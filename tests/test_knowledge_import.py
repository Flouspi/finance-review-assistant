import json
from pathlib import Path
import unittest
from unittest.mock import patch

from finance_assistant.config import ROOT
from finance_assistant.providers import LocalKnowledge
from finance_assistant.workbook_import import convert_workbook
from finance_assistant.workflow import as_text


class WorkbookKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / "sources" / "智合规_金融合规知识库_v1.0.xlsx"
        cls.records, cls.report = convert_workbook(cls.source)
        cls.provider = LocalKnowledge(ROOT / "knowledge")

    def test_all_selected_rows_preserved_and_no_prompt_sheets(self):
        self.assertEqual(self.report["record_count"], 1889)
        self.assertEqual(self.report["sheets"], {"01_法规条款": 1463, "02_监管规则": 368, "03_监管案例": 5,
                                               "04_市场披露": 15, "05_司法案例": 6, "06_风险规则": 32})
        imported = [json.loads(line) for line in (ROOT / "knowledge" / "智合规_v1.0.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(imported, self.records)
        self.assertEqual(len({r["id"] for r in imported}), 1889)
        self.assertFalse(any(r["sheet"] in {"08_Agent提示词", "09_程序接入", "00_总览", "07_来源清单"} for r in imported))

    def test_real_retrieval_preserves_provenance_without_network(self):
        queries = [("民法典 第一百四十三条 民事法律行为 有效", "LAW-民法典-第一百四十三条"),
                   ("对外担保未履行公司决议", "RULE-001"),
                   ("银行 保证期间 主张保证责任 征信", "CASE-RM-003"),
                   ("证券虚假陈述 会计师事务所 连带责任", "CASE-RM-002")]
        with patch("finance_assistant.providers.httpx.post", side_effect=AssertionError("Retrieval must be offline")):
            for query, expected in queries:
                with self.subTest(query=query):
                    hits, _ = self.provider.retrieve(query)
                    self.assertEqual(hits[0]["record_id"], expected)
                    self.assertTrue(hits[0]["source_url"] or hits[0]["sheet"] == "06_风险规则")
                    self.assertEqual(hits[0]["source_sha256"], self.report["source_sha256"])
                    context = as_text(hits)
                    self.assertIn(hits[0]["location"], context)
                    self.assertIn(hits[0]["evidence_type"], context)

    def test_metadata_and_rules_keep_their_distinct_evidence_type(self):
        by_id = {r["id"]: r for r in self.records}
        self.assertEqual(by_id["DISC-CNINFO-001"]["evidence_type"], "市场披露（元数据级）")
        self.assertIn("人工整理", by_id["RULE-001"]["evidence_type"])
        self.assertIn("正文需下载PDF", by_id["DISC-CNINFO-001"]["verification_status"])


if __name__ == "__main__":
    unittest.main()
