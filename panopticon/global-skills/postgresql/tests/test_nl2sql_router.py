#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nl2sql_router import (  # noqa: E402
    build_param_hints,
    filter_templates_by_allowlist,
    load_templates,
    parse_allowlist,
    route_query,
)


class TestNL2SQLRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.templates = load_templates(ROOT / "nl2sql_templates.json")

    def test_signup_query_routing(self):
        matches = route_query("上周新注册用户有多少", self.templates, top_k=3, min_score=0.0)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].template_id, "t01_new_users_in_range")

    def test_refund_query_routing(self):
        matches = route_query("最近7天退款率", self.templates, top_k=3, min_score=0.0)
        self.assertGreaterEqual(len(matches), 1)
        top_ids = [m.template_id for m in matches]
        self.assertIn("t08_refund_rate", top_ids)

    def test_param_hint_generation(self):
        hints = build_param_hints(["start_time", "end_time", "top_n"])
        self.assertEqual(len(hints), 3)
        self.assertEqual(hints[0]["name"], "start_time")
        self.assertIn("开始时间", hints[0]["hint"])

    def test_parse_allowlist(self):
        allow = parse_allowlist("users, orders , sessions")
        self.assertEqual(allow, {"users", "orders", "sessions"})

    def test_strict_allowlist_filter(self):
        # 只允许 users，则需要 refunds / orders 等表的模板应被过滤
        kept, dropped_ids = filter_templates_by_allowlist(self.templates, {"users"})
        kept_ids = {t.get("id") for t in kept}
        self.assertIn("t01_new_users_in_range", kept_ids)
        self.assertIn("t08_refund_rate", set(dropped_ids))

    def test_routing_after_allowlist(self):
        kept, _ = filter_templates_by_allowlist(self.templates, {"users"})
        matches = route_query("最近7天退款率", kept, top_k=3, min_score=0.0)
        if matches:
            ids = [m.template_id for m in matches]
            self.assertNotIn("t08_refund_rate", ids)


if __name__ == "__main__":
    unittest.main()
