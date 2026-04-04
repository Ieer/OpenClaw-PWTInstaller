#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "knowledge_eval.py"
SPEC = importlib.util.spec_from_file_location("knowledge_eval", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"failed to load module spec from {MODULE_PATH}")
knowledge_eval = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = knowledge_eval
SPEC.loader.exec_module(knowledge_eval)

EvalConfig = knowledge_eval.EvalConfig
build_payload = knowledge_eval.build_payload
normalize_api_base = knowledge_eval.normalize_api_base
resolve_endpoint_from_env = knowledge_eval.resolve_endpoint_from_env
summarize_response = knowledge_eval.summarize_response


class TestKnowledgeEval(unittest.TestCase):
    def setUp(self) -> None:
        self.config = EvalConfig(
            resolve_url="http://localhost:18910/v1/knowledge/resolve",
            token="token",
            default_agent_slug="metrics",
            default_risk_level="normal",
            default_limit=5,
        )

    def test_normalize_api_base_from_events(self):
        self.assertEqual(normalize_api_base("http://localhost:18910/v1/events"), "http://localhost:18910")

    def test_normalize_api_base_from_resolve(self):
        self.assertEqual(
            normalize_api_base("http://localhost:18910/v1/knowledge/resolve"),
            "http://localhost:18910",
        )

    def test_resolve_endpoint_from_event_env(self):
        old = os.environ.get("EVENT_HTTP_URL")
        try:
            os.environ["EVENT_HTTP_URL"] = "http://localhost:18910/v1/events"
            self.assertEqual(
                resolve_endpoint_from_env(),
                "http://localhost:18910/v1/knowledge/resolve",
            )
        finally:
            if old is None:
                os.environ.pop("EVENT_HTTP_URL", None)
            else:
                os.environ["EVENT_HTTP_URL"] = old

    def test_build_payload_uses_defaults(self):
        payload = build_payload(
            task="评估指标异常是否需要升级处理",
            agent_slug="",
            risk_level="",
            tags=["metric", "analysis"],
            limit=None,
            retrieval_mode="",
            ranking_profile="",
            source_type="",
            semantic_query="",
            semantic_limit=None,
            min_semantic_similarity=None,
            min_score=None,
            require_approved_validation=None,
            include_rejected=False,
            config=self.config,
        )
        self.assertEqual(payload["agent_slug"], "metrics")
        self.assertEqual(payload["risk_level"], "normal")
        self.assertEqual(payload["limit"], 5)
        self.assertEqual(payload["retrieval_mode"], "hybrid")
        self.assertEqual(payload["ranking_profile"], "balanced")

    def test_summarize_ok_response(self):
        response = {
            "items": [
                {
                    "unit": {"unit_key": "rule-1", "title": "Rule One", "risk_level": "high"},
                    "validation_status": "approved",
                    "score": 1.2,
                    "retrieval_channels": ["hybrid"],
                }
            ],
            "rejected": [],
        }
        summary = summarize_response(response, None)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["selected_count"], 1)

    def test_summarize_rejected_only(self):
        response = {
            "items": [],
            "rejected": [{"reason": "missing approved validation"}],
        }
        summary = summarize_response(response, None)
        self.assertEqual(summary["status"], "rejected_only")

    def test_summarize_no_hit(self):
        summary = summarize_response({"items": [], "rejected": []}, None)
        self.assertEqual(summary["status"], "no_hit")


if __name__ == "__main__":
    unittest.main()