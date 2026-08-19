import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.exports import export_all
from agent.pipeline import _score_supplier, run_pipeline, stage4_scoring, stage7_decision
from agent.toolkit import ToolLog


class PipelineTests(unittest.TestCase):
    def supplier(self, grade="B", legal=True, official=True):
        return {
            "name": "Acme Export Company Limited",
            "legal_name": "Acme Export Company Limited" if legal else "",
            "official_website": "https://acme.example" if official else "",
            "profile_url": "https://acme.example/product",
            "url": "https://acme.example/product",
            "country": "Turkey",
            "candidate_grade": grade,
            "identity_status": "supported_public_identity",
            "entity_method": "page_structured_data",
            "entity_confidence": 0.95,
            "product_match": 0.90,
            "product_evidence": "Acme manufactures and exports the required product.",
            "contact": "sales@acme.example",
            "year_founded": "2005",
            "certs_mentioned": ["ISO 9001", "CE"],
            "certs_verified": [],
            "signals": {"mentions_export": True, "mentions_factory": True, "mentions_moq": True, "mentions_terms": True, "has_contact": True, "capacity_numbers": ["1000 units per month"]},
            "source_ids": ["abc123"],
            "discovery_urls": ["https://acme.example/product"],
            "eligible_for_scoring": True,
            "key": "acmeexport",
            "source_channel": "وب‌سایت مستقل/وب عمومی",
            "source_tool": "Public web search (ddgs)",
            "company_type": "manufacturer",
            "related_product": "Test product",
            "checked_on": "2026-08-16",
            "snippet": "manufacturer exporter MOQ FOB sample",
        }

    def test_scoring_caps_unverified_claims_and_response(self):
        result = _score_supplier(self.supplier())
        self.assertLessEqual(result["scores"]["certs"], 2)
        self.assertEqual(result["scores"]["response"], 0)
        self.assertTrue(result["eligible_for_top5"])

    def test_c_grade_cannot_enter_top5(self):
        s = self.supplier(grade="C", legal=False, official=False)
        scored = stage4_scoring({"longlist": [s]}, {"name_en": "Test product"}, lambda *args: None, ToolLog())
        self.assertEqual(scored["top5"], [])

    def test_no_forced_decision(self):
        card = {"name": "Weak Candidate", "total": 70, "citation_grade": "C — شواهد ضعیف", "rfq_eligible": False, "green_flags": [], "red_flags": ["هویت ضعیف"], "country": "نامشخص", "email": "یافت نشد"}
        decision = stage7_decision([card], {}, lambda *args: None, ToolLog())
        self.assertEqual(decision["recommendation_status"], "not_ready")
        self.assertEqual(decision["first_choice"], "")

    def test_readiness_summary_is_built(self):
        inp = {"name_fa": "کالا", "name_en": "Sample widget", "specs": "220V", "qty_hint": "10 units"}
        with patch("agent.toolkit.run_queries", return_value=[]), patch("agent.webutil.fetch_many", return_value={}):
            dossier = run_pipeline(inp, lambda *args: None)
        summary = dossier["summary"]
        self.assertIn("score", summary)
        self.assertIn("stages", summary)
        self.assertIn("metrics", summary)
        self.assertIn("product", summary["stages"])
        self.assertEqual(summary["score"], summary["score"])

    def test_empty_web_run_still_exports_honest_files(self):
        inp = {"name_fa": "محصول آزمایشی", "name_en": "Test industrial widget", "specs": "Grade A, 220V", "qty_hint": "10 units", "owner_fa": "", "owner_en": "", "buyer_city": "Tehran, Iran"}
        with patch("agent.toolkit.run_queries", return_value=[]), patch("agent.webutil.fetch_many", return_value={}):
            dossier = run_pipeline(inp, lambda *args: None)
        self.assertEqual(dossier["sourcing"]["longlist"], [])
        self.assertEqual(dossier["decision"]["recommendation_status"], "not_ready")
        self.assertEqual(dossier["meta"]["developer_en"], "Setayesh Jafari")
        self.assertEqual(dossier["meta"]["agent_version"], "4.1-premium")
        self.assertNotIn("course", dossier["meta"])
        self.assertNotIn("student_fa", dossier["meta"])
        with tempfile.TemporaryDirectory() as td:
            files = export_all(dossier, Path(td))
            self.assertEqual(set(files), {"report", "excel", "rfq", "prompts"})
            for name in files.values():
                self.assertTrue((Path(td) / name).exists())


if __name__ == "__main__":
    unittest.main()
