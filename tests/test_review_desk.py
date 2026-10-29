import json
import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from finance_assistant.config import ROOT
from finance_assistant.ui_reports import ReportModel, bind_report, parse_report, risk_counts
from test_workflow import FakeKnowledge


def sample_report():
    return {"summary": "测试结果，待核实。", "overall_risk": "高", "answer_markdown": "审查结果：测试意见。",
            "findings": [{"title": "回购义务主体需明确", "level": "高", "clause": "第3.2条",
                          "quote": "公司承担连带回购责任", "reason": "测试风险描述", "recommendation": "测试建议",
                          "revision": "建议替换文本，需核对。", "evidence_ids": [1, 999]}]}


class StructuredModel:
    def __init__(self):
        self.requests = []

    def complete(self, messages, config):
        self.requests.append(messages)
        if len(self.requests) % 2:
            return "合同审查"
        result = sample_report()
        result["answer_markdown"] += f" 第{len(self.requests) // 2}轮。"
        return json.dumps(result, ensure_ascii=False)


class StructuredReportTests(unittest.TestCase):
    def test_quote_match_and_only_available_evidence(self):
        parsed = parse_report(json.dumps(sample_report(), ensure_ascii=False))
        bound = bind_report(parsed, [{"source": "test"}], "第3.2条 公司承担连带回购责任。")
        item = bound["findings"][0]
        self.assertTrue(item["quote_located"])
        self.assertEqual(item["evidence_ids"], [1])
        self.assertTrue(item["unavailable_evidence"])
        self.assertEqual(risk_counts(bound), {"高": 1, "中": 0, "低": 0, "待核实": 0})
        self.assertEqual(parsed["findings"][0]["evidence_ids"], [1, 999])

    def test_missing_structure_does_not_imply_zero_risk(self):
        self.assertIsNone(parse_report("风险等级：高。请进一步核查。"))
        self.assertIsNone(parse_report('{"findings": []}'))
        self.assertIsNone(risk_counts(None))
        data = sample_report()
        data["overall_risk"] = {"invalid": "type"}
        data["findings"][0]["level"] = ["高"]
        report = parse_report(json.dumps(data))
        self.assertEqual(report["overall_risk"], "待核实")
        self.assertEqual(report["findings"][0]["level"], "待核实")

    def test_unmatched_quote_is_not_claimed_as_located(self):
        data = sample_report()
        data["findings"][0]["quote"] = "材料中不存在的原文"
        report = bind_report(parse_report(json.dumps(data)), [], "已提供材料")
        self.assertFalse(report["findings"][0]["quote_located"])
        self.assertEqual(report["findings"][0]["evidence_ids"], [])

    def test_adapter_keeps_classifier_unchanged_and_uses_two_calls(self):
        model = StructuredModel()
        adapter = ReportModel(model)
        classifier = [{"role": "system", "content": "分类器"}]
        self.assertEqual(adapter.complete(classifier, {}), "合同审查")
        self.assertEqual(model.requests[0], classifier)
        text = adapter.complete([{"role": "system", "content": "审查内容"}], {})
        self.assertEqual(len(model.requests), 2)
        self.assertIn("测试意见", text)
        self.assertEqual(adapter.report["overall_risk"], "高")


class ReviewDeskTests(unittest.TestCase):
    def test_review_followup_history_and_manual_flag(self):
        with patch.dict(os.environ, {}, clear=True):
            app = AppTest.from_file(str(ROOT / "judge_app.py"), default_timeout=20)
            app.secrets.update({"MODEL_API_KEY": "not-a-real-key"})
            app.run()
            model = StructuredModel()
            with patch("finance_assistant.providers.ChatModel", return_value=model), patch("finance_assistant.providers.knowledge_provider", return_value=FakeKnowledge()):
                next(x for x in app.text_area if x.label == "审查内容").set_value("请审查合同：第3.2条 公司承担连带回购责任。")
                next(x for x in app.button if x.label == "开始审查").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.session_state.reviews), 1)
                case = app.session_state.reviews[0]
                self.assertTrue(case["report"]["findings"][0]["quote_located"])
                next(x for x in app.text_area if x.label == "审查内容").set_value("请进一步解释该条款。")
                next(x for x in app.button if x.label == "开始审查").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.session_state.reviews), 1)
                self.assertEqual(len(app.session_state.reviews[0]["turns"]), 2)
                self.assertIn("第1轮", app.session_state.reviews[0]["turns"][0]["answer"])
                self.assertIn("第2轮", app.session_state.reviews[0]["turns"][1]["answer"])
                self.assertIn("公司承担连带回购责任", "\n".join(x["content"] for x in model.requests[2]))
            next(x for x in app.button if x.label == "标记人工复核").click().run()
            self.assertTrue(app.session_state.reviews[0]["human_review"])
            next(x for x in app.button if x.label == "＋  新建审查").click().run()
            self.assertIsNone(app.session_state.active_review)
            self.assertEqual(len(app.session_state.reviews), 1)
            next(x for x in app.button if x.key == "history_0").click().run()
            self.assertEqual(app.session_state.active_review, 0)
            self.assertEqual(len(app.exception), 0)

    def test_new_session_does_not_show_other_reviews(self):
        with patch.dict(os.environ, {"EVALUATION_MODE": "true"}):
            app = AppTest.from_file(str(ROOT / "judge_app.py"), default_timeout=20).run()
            self.assertEqual(len(app.session_state.reviews), 0)
            self.assertEqual(len(app.exception), 0)
