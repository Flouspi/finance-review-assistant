from io import BytesIO
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager

import httpx
from docx import Document
from streamlit.testing.v1 import AppTest

from finance_assistant.config import ROOT, Settings
from finance_assistant.documents import InputError, extract
from finance_assistant.providers import ChatModel, LocalKnowledge, ProviderError, ConfigurationError, knowledge_provider
from finance_assistant.workflow import Workflow, WorkflowError, load_dsl, CATEGORIES, CLASSIFIER, CONTRACT_REVIEW, CONTRACT_RETRIEVER, GENERAL_RETRIEVER, GENERAL_REVIEW, report_markdown


@contextmanager
def retained_test_directory():
    # Keep test artifacts; the user's workspace policy prohibits bulk deletion.
    directory = ROOT / ".runtime" / "testdata"
    directory.mkdir(parents=True, exist_ok=True)
    yield tempfile.mkdtemp(prefix="case-", dir=directory)


class FakeModel:
    def __init__(self, category="合同审查"):
        self.category = category
        self.calls = []

    def complete(self, messages, config):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return self.category
        return "审查结果：\n- 风险等级：待核实\n- 主要问题：测试输出\n- 合规依据：[证据1]\n- 修改建议：补充资料"


class FakeKnowledge:
    def __init__(self):
        self.queries = []

    def retrieve(self, query, top_k=4):
        self.queries.append((query, top_k))
        return [{"id": "test-rule", "source": "测试规则（非真实法规）", "location": "第1段", "content": "仅用于测试的法规占位文本", "score": 1}], []


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.dsl = load_dsl()

    def test_all_five_corrected_paths(self):
        for category in CATEGORIES:
            with self.subTest(category=category):
                model, kb = FakeModel(category), FakeKnowledge()
                w = Workflow(self.dsl, model, kb)
                result = w.invoke("请审查本产品投资比例及合同细则", [{"name": "条款.txt", "data": "独特合同正文ABC123".encode()}])
                self.assertEqual(result["category"], category)
                self.assertTrue(result["answer"])
                self.assertEqual(len(model.calls), 2)
                self.assertEqual(len(kb.queries), 1)
                self.assertEqual(kb.queries[0][1], 4)
                self.assertIn("独特合同正文ABC123", kb.queries[0][0])
                final_prompt = "\n".join(x["content"] for x in model.calls[-1])
                self.assertIn("独特合同正文ABC123", final_prompt)
                self.assertIn("仅用于测试的法规占位文本", final_prompt)
                self.assertEqual(result["trace"][0]["node_id"], "prepare_documents")
                if category == "其他":
                    ids = [x["node_id"] for x in result["trace"]]
                    self.assertLess(ids.index(GENERAL_RETRIEVER), ids.index(GENERAL_REVIEW))

    def test_original_contract_preserves_wrong_wiring(self):
        model, kb = FakeModel(), FakeKnowledge()
        result = Workflow(self.dsl, model, kb, "faithful").invoke("审查合同", [{"name": "x.txt", "data": "原始合同正文".encode()}])
        self.assertEqual(kb.queries[0][0], "合同审查")
        final_prompt = model.calls[-1][0]["content"]
        self.assertIn("# 合同文本\n合同审查", final_prompt)
        self.assertIn("# 知识库参考资料\n【材料：x.txt】\n原始合同正文", final_prompt)
        self.assertNotIn("仅用于测试的法规占位文本", final_prompt)
        self.assertTrue(result["answer"])

    def test_original_general_surfaces_dangling_reference(self):
        with self.assertRaisesRegex(WorkflowError, GENERAL_RETRIEVER):
            Workflow(self.dsl, FakeModel("其他"), FakeKnowledge(), "faithful").invoke("你好")

    def test_original_other_three_review_paths(self):
        for category in CATEGORIES[1:4]:
            result = Workflow(self.dsl, FakeModel(category), FakeKnowledge(), "faithful").invoke("审查内容")
            self.assertTrue(result["answer"])

    def test_classifier_fallback_and_original_missing_default(self):
        result = Workflow(self.dsl, FakeModel("不能分类"), FakeKnowledge()).invoke("问题")
        self.assertEqual(result["category"], "其他")
        self.assertTrue(result["warnings"])
        with self.assertRaises(WorkflowError):
            Workflow(self.dsl, FakeModel("不能分类"), FakeKnowledge(), "faithful").invoke("问题")

    def test_contract_priority_matches_original_contains_order(self):
        result = Workflow(self.dsl, FakeModel("合同审查 产品合规审查"), FakeKnowledge()).invoke("问题")
        self.assertEqual(result["category"], "合同审查")
        self.assertIn(CONTRACT_REVIEW, [x["node_id"] for x in result["trace"]])

    def test_original_dsl_not_mutated(self):
        import copy
        before = copy.deepcopy(self.dsl)
        Workflow(self.dsl, FakeModel(), FakeKnowledge())
        self.assertEqual(before, self.dsl)

    def test_repeated_run_has_no_cross_case_leakage(self):
        # New calls reset all state; history is UI-only, as in the export.
        class SequentialModel:
            def complete(self, messages, config):
                if "分类器" in "".join(m["content"] for m in messages):
                    return "合同审查"
                return "测试结果"
        w = Workflow(self.dsl, SequentialModel(), FakeKnowledge())
        w.invoke("FIRST-CASE")
        state = w.invoke("SECOND-CASE")
        self.assertNotIn("FIRST-CASE", str(state))

    def test_file_only_input_and_limits(self):
        w = Workflow(self.dsl, FakeModel(), FakeKnowledge(), max_input_chars=50)
        self.assertTrue(w.invoke("", [{"name": "x.txt", "data": "合同".encode()}])["answer"])
        with self.assertRaises(InputError):
            w.invoke("")
        with self.assertRaises(InputError):
            w.invoke("x" * 51)
        with self.assertRaises(InputError):
            w.invoke("合同", [{"name": "x.txt", "data": b"x" * 50}])
        with self.assertRaises(InputError):
            w.invoke("合同", [{"name": "x.txt", "data": b"x"}] * 4)

    def test_empty_kb_warns_and_guard_requires_insufficient_evidence(self):
        with retained_test_directory() as tmp:
            model = FakeModel()
            state = Workflow(self.dsl, model, LocalKnowledge(Path(tmp))).invoke("审查合同")
            self.assertEqual(state["citations"], [])
            self.assertIn("知识库为空", " ".join(state["warnings"]))
            self.assertIn("不得给出确定的合规通过结论", model.calls[-1][0]["content"])

    def test_report_excludes_runtime_data(self):
        state = Workflow(self.dsl, FakeModel(), FakeKnowledge()).invoke("test")
        state["values"]["secret"] = "DO-NOT-EXPORT"
        report = report_markdown(state, "corrected")
        self.assertNotIn("DO-NOT-EXPORT", report)
        self.assertIn("测试规则", report)


class InputAndProviderTests(unittest.TestCase):
    def test_document_paragraph_table_order(self):
        doc = Document()
        doc.add_paragraph("开始段落")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "条款A"
        table.cell(0, 1).text = "条款B"
        doc.add_paragraph("结束段落")
        buffer = BytesIO()
        doc.save(buffer)
        text = extract("合同.docx", buffer.getvalue())
        self.assertLess(text.index("开始段落"), text.index("条款A"))
        self.assertLess(text.index("条款B"), text.index("结束段落"))

    def test_text_encodings_and_bad_files(self):
        self.assertEqual(extract("x.txt", "合同正文".encode("gb18030")), "合同正文")
        for name, content in [("x.png", b"image"), ("x.pdf", b"corrupt"), ("x.docx", b"bad"), ("x.txt", b" ")]:
            with self.subTest(name=name), self.assertRaises(InputError):
                extract(name, content)

    def test_pdf_blank_page_rejected(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buffer = BytesIO()
        writer.write(buffer)
        with self.assertRaisesRegex(InputError, "无可提取文字"):
            extract("scan.pdf", buffer.getvalue())

    def test_local_retrieval_ranks_and_has_provenance(self):
        with retained_test_directory() as tmp:
            directory = Path(tmp)
            (directory / "contract.txt").write_text("合同审查 合同条款 违约责任 投资人权利" * 5, encoding="utf-8")
            (directory / "other.txt").write_text("苹果香蕉水果", encoding="utf-8")
            result, warnings = LocalKnowledge(directory).retrieve("合同条款 违约责任", 1)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["source"], "contract.txt")
            self.assertTrue(result[0]["location"])
            self.assertEqual(warnings, [])
            self.assertEqual(len(result[0]["source_sha256"]), 64)

    def test_model_http_payload_and_error_redaction(self):
        settings = Settings(api_key="SECRET-DO-NOT-PRINT")
        config = {"name": "deepseek-flash", "completion_params": {"temperature": .7, "thinking": False}}
        response = httpx.Response(200, json={"choices": [{"message": {"content": "合同审查"}}]}, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))
        with patch("finance_assistant.providers.httpx.post", return_value=response) as call:
            self.assertEqual(ChatModel(settings).complete([{"role": "system", "content": "test"}], config), "合同审查")
            self.assertEqual(call.call_args.kwargs["json"]["thinking"], {"type": "disabled"})
            self.assertEqual(call.call_args.kwargs["json"]["temperature"], .7)
        bad = httpx.Response(401, text="SECRET-DO-NOT-PRINT", request=response.request)
        with patch("finance_assistant.providers.httpx.post", return_value=bad), self.assertRaises(ProviderError) as error:
            ChatModel(settings).complete([], config)
        self.assertNotIn("SECRET-DO-NOT-PRINT", str(error.exception))

    def test_missing_model_key(self):
        with self.assertRaises(ConfigurationError):
            ChatModel(Settings()).complete([], {"name": "deepseek-flash"})

    def test_own_knowledge_never_calls_external_service(self):
        with retained_test_directory() as tmp:
            directory = Path(tmp)
            (directory / "测试制度.txt").write_text("合同条款 违约责任 信息披露" * 80, encoding="utf-8")
            provider = knowledge_provider(Settings(knowledge_dir=directory))
            with patch("finance_assistant.providers.httpx.post", side_effect=AssertionError("Knowledge retrieval must not make network calls")):
                status = provider.status()
                records, warnings = provider.retrieve("合同违约责任")
            self.assertTrue(status["ready"])
            self.assertEqual(status["file_count"], 1)
            self.assertGreater(status["chunk_count"], 1)
            self.assertTrue(records)
            self.assertEqual(records[0]["source_sha256"], status["documents"][0]["sha256"])
            self.assertEqual(warnings, [])


class InterfaceTests(unittest.TestCase):
    def test_public_entrypoint_always_uses_reviewer_mode(self):
        with patch.dict(os.environ, {"EVALUATION_MODE": "false"}, clear=True):
            app = AppTest.from_file(str(ROOT / "judge_app.py"), default_timeout=20)
            app.secrets.update({"EVALUATION_MODE": False})
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.text_input), 0)
            self.assertEqual(len(app.selectbox), 0)
            self.assertTrue(next(b for b in app.button if b.label == "开始审查").disabled)

    def test_cloud_config_and_environment_precedence(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.load({"MODEL_API_KEY": "cloud-test-key", "EVALUATION_MODE": True,
                                      "KNOWLEDGE_BACKEND": "dify"})
            self.assertTrue(settings.evaluation_mode)
            self.assertEqual(settings.api_key, "cloud-test-key")
            self.assertEqual(settings.knowledge_backend, "local")
        with patch.dict(os.environ, {"MODEL_API_KEY": "environment-test-key"}):
            self.assertEqual(Settings.load({"MODEL_API_KEY": "cloud-test-key"}).api_key, "environment-test-key")

    def test_reviewer_mode_hides_connection_controls_and_submits(self):
        with retained_test_directory() as tmp, patch.dict(os.environ, {"KNOWLEDGE_DIR": tmp}, clear=True):
            (Path(tmp) / "测试制度.txt").write_text("测试制度，非真实法规。合同条款需核对。", encoding="utf-8")
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
            app.secrets.update({"EVALUATION_MODE": True, "MODEL_API_KEY": "cloud-test-key",
                                "KNOWLEDGE_BACKEND": "local"})
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.text_input), 0)
            self.assertEqual(len(app.selectbox), 0)
            model = FakeModel("合同审查")
            with patch("finance_assistant.providers.ChatModel", return_value=model), patch("finance_assistant.providers.knowledge_provider", return_value=FakeKnowledge()):
                app.text_area[0].set_value("请审查合同条款")
                next(b for b in app.button if b.label == "开始审查").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.session_state.reviews), 1)
            self.assertEqual(app.session_state.reviews[0]["mode"], "corrected")
            visible = " ".join(str(x.value) for x in app.markdown)
            self.assertNotIn("cloud-test-key", visible)

    def test_reviewer_mode_blocks_unconfigured_service(self):
        with patch.dict(os.environ, {}, clear=True):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
            app.secrets.update({"EVALUATION_MODE": True, "MODEL_API_KEY": "", "KNOWLEDGE_BACKEND": "dify"})
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(next(b for b in app.button if b.label == "开始审查").disabled)
            self.assertTrue(any("尚未完成配置" in x.value for x in app.error))

    def test_app_renders_and_submit(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
        app.run()
        self.assertEqual(len(app.exception), 0)
        model = FakeModel("营销宣传合规审查")
        with patch("finance_assistant.providers.ChatModel", return_value=model), patch("finance_assistant.providers.knowledge_provider", return_value=FakeKnowledge()):
            app.text_input[0].set_value("test-key-not-real")
            app.text_area[0].set_value("请检查宣传文案：示例材料")
            next(b for b in app.button if b.label == "开始审查").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.session_state.reviews), 1)
        self.assertEqual(app.session_state.reviews[0]["state"]["category"], "营销宣传合规审查")


if __name__ == "__main__":
    unittest.main()
