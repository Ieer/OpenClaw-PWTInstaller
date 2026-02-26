#!/usr/bin/env python3
from __future__ import annotations

import unittest

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from postgresql_skill import PostgreSQLSkill  # noqa: E402


class TestPostgreSQLSkill(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = PostgreSQLSkill({}, allowed_tables=["users", "orders"], max_rows=100)

    def test_validate_read_only_select(self):
        ok, reason = self.skill.validate_read_only_sql("SELECT * FROM users")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_validate_read_only_with(self):
        ok, reason = self.skill.validate_read_only_sql(
            "WITH t AS (SELECT 1 AS x) SELECT x FROM t"
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_reject_write_sql(self):
        ok, reason = self.skill.validate_read_only_sql("DELETE FROM users WHERE id = %s")
        self.assertFalse(ok)
        self.assertTrue(
            ("only SELECT/WITH" in (reason or ""))
            or ("forbidden keyword" in (reason or ""))
        )

    def test_reject_multistatement_sql(self):
        ok, reason = self.skill.validate_read_only_sql("SELECT 1; SELECT 2;")
        self.assertFalse(ok)
        self.assertIn("multiple statements", reason or "")

    def test_limit_enforced_when_missing(self):
        out = self.skill.enforce_limit("SELECT * FROM users")
        self.assertIn("LIMIT 100", out.upper())

    def test_limit_not_overwritten(self):
        out = self.skill.enforce_limit("SELECT * FROM users LIMIT 10")
        self.assertEqual(out, "SELECT * FROM users LIMIT 10")

    def test_allowlist_table_ok(self):
        ok, reason = self.skill.ensure_table_allowed("users")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_allowlist_table_blocked(self):
        ok, reason = self.skill.ensure_table_allowed("payments")
        self.assertFalse(ok)
        self.assertIn("table not allowed", reason or "")

    def test_identifier_validation(self):
        ok, reason = self.skill.ensure_table_allowed("users;drop table users")
        self.assertFalse(ok)
        self.assertIn("invalid table identifier", reason or "")


if __name__ == "__main__":
    unittest.main()
