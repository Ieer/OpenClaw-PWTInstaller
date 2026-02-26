#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from postgresql_skill import PostgreSQLSkill, load_connection_params_from_env  # noqa: E402


def main() -> int:
    allowed = [t.strip() for t in os.getenv("PG_ALLOWED_TABLES", "").split(",") if t.strip()]
    max_rows = int(os.getenv("PG_MAX_ROWS", "1000"))

    with PostgreSQLSkill(load_connection_params_from_env(), allowed_tables=allowed, max_rows=max_rows) as skill:
        if skill.connection is None:
            print("connect failed: check PG* env and psycopg2 installation")
            return 1

        result = skill.query_safe("SELECT now() AS ts, current_database() AS db", ())
        print(result.to_json())
        return 0 if result.success else 2


if __name__ == "__main__":
    raise SystemExit(main())
