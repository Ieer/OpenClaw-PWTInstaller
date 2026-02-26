#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

try:
    import psycopg2  # type: ignore
    from psycopg2 import Error as PsycopgError  # type: ignore
    from psycopg2.extras import RealDictCursor  # type: ignore

    HAS_PSYCOPG2 = True
except Exception:
    psycopg2 = None
    RealDictCursor = None
    HAS_PSYCOPG2 = False

    class PsycopgError(Exception):
        pass


FORBIDDEN_SQL_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "merge",
    "upsert",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "do",
    "call",
    "vacuum",
    "analyze",
    "refresh",
}


def _normalize_sql(sql_text: str) -> str:
    compact = re.sub(r"\s+", " ", sql_text).strip()
    return compact


def _sql_fingerprint(sql_text: str) -> str:
    normalized = _normalize_sql(sql_text).lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


@dataclass
class QueryResult:
    success: bool
    data: list[dict[str, Any]]
    count: int
    error: str | None
    meta: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "data": self.data,
                "count": self.count,
                "error": self.error,
                "meta": self.meta,
            },
            ensure_ascii=False,
            indent=2,
        )


class PostgreSQLSkill:
    def __init__(
        self,
        connection_params: dict[str, Any],
        *,
        allowed_tables: Iterable[str] | None = None,
        max_rows: int = 1000,
    ):
        self.connection_params = connection_params
        self.allowed_tables = {t.strip() for t in (allowed_tables or []) if t.strip()}
        self.max_rows = max(1, int(max_rows))
        self.connection = None

    def connect(self) -> bool:
        if not HAS_PSYCOPG2:
            return False
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            return True
        except Exception:
            self.connection = None
            return False

    def disconnect(self) -> None:
        if self.connection:
            try:
                self.connection.close()
            finally:
                self.connection = None

    def __enter__(self) -> "PostgreSQLSkill":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    @staticmethod
    def validate_read_only_sql(query: str) -> tuple[bool, str | None]:
        q = query.strip()
        if not q:
            return False, "empty query"

        semicolon_count = q.count(";")
        if semicolon_count > 1:
            return False, "multiple statements are not allowed"
        if semicolon_count == 1 and not q.endswith(";"):
            return False, "semicolon is only allowed at query end"

        q_clean = q[:-1].strip() if q.endswith(";") else q
        q_low = q_clean.lower()

        if not (q_low.startswith("select") or q_low.startswith("with")):
            return False, "only SELECT/WITH queries are allowed"

        for kw in FORBIDDEN_SQL_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", q_low):
                return False, f"forbidden keyword detected: {kw}"

        return True, None

    def enforce_limit(self, query: str) -> str:
        q = query.strip()
        q_no_tail = q[:-1].strip() if q.endswith(";") else q
        has_limit = re.search(r"\blimit\s+\d+\b", q_no_tail, flags=re.IGNORECASE) is not None
        if has_limit:
            return q
        return f"{q_no_tail} LIMIT {self.max_rows};"

    def ensure_table_allowed(self, table_name: str) -> tuple[bool, str | None]:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name or ""):
            return False, "invalid table identifier"
        if self.allowed_tables and table_name not in self.allowed_tables:
            return False, f"table not allowed: {table_name}"
        return True, None

    def query_safe(self, query: str, params: tuple[Any, ...] | list[Any] | None = None) -> QueryResult:
        ok, reason = self.validate_read_only_sql(query)
        if not ok:
            return QueryResult(
                success=False,
                data=[],
                count=0,
                error=reason,
                meta={"fingerprint": _sql_fingerprint(query), "blocked": True},
            )

        if self.connection is None:
            return QueryResult(
                success=False,
                data=[],
                count=0,
                error="not connected to database",
                meta={"fingerprint": _sql_fingerprint(query), "blocked": False},
            )

        safe_query = self.enforce_limit(query)
        fingerprint = _sql_fingerprint(safe_query)

        try:
            if RealDictCursor is not None:
                cursor_ctx = self.connection.cursor(cursor_factory=RealDictCursor)
            else:
                cursor_ctx = self.connection.cursor()

            with cursor_ctx as cursor:
                cursor.execute(safe_query, tuple(params or ()))
                rows = cursor.fetchall()

                if rows and isinstance(rows[0], dict):
                    out = [
                        {key: _serialize_value(value) for key, value in row.items()}  # type: ignore[union-attr]
                        for row in rows
                    ]
                else:
                    columns = [d[0] for d in (cursor.description or [])]
                    out = []
                    for row in rows:
                        out.append({col: _serialize_value(val) for col, val in zip(columns, row)})

                return QueryResult(
                    success=True,
                    data=out,
                    count=len(out),
                    error=None,
                    meta={"fingerprint": fingerprint, "blocked": False, "limited": True},
                )
        except PsycopgError as exc:
            return QueryResult(
                success=False,
                data=[],
                count=0,
                error=f"database error: {exc}",
                meta={"fingerprint": fingerprint, "blocked": False},
            )
        except Exception as exc:
            return QueryResult(
                success=False,
                data=[],
                count=0,
                error=f"unexpected error: {exc.__class__.__name__}",
                meta={"fingerprint": fingerprint, "blocked": False},
            )


def load_connection_params_from_env() -> dict[str, Any]:
    return {
        "host": os.getenv("PGHOST", "127.0.0.1"),
        "port": int(os.getenv("PGPORT", "5432")),
        "database": os.getenv("PGDATABASE", "postgres"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PostgreSQL read-only query skill")
    parser.add_argument("--query", required=True, help="SQL query, SELECT/WITH only")
    parser.add_argument("--params", default="[]", help="JSON array for query parameters")
    parser.add_argument("--max-rows", type=int, default=int(os.getenv("PG_MAX_ROWS", "1000")))
    parser.add_argument(
        "--allowed-tables",
        default=os.getenv("PG_ALLOWED_TABLES", ""),
        help="comma separated table allowlist",
    )
    args = parser.parse_args()

    try:
        params = json.loads(args.params)
        if not isinstance(params, list):
            raise ValueError("params must be a JSON array")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "data": [],
                    "count": 0,
                    "error": f"invalid --params: {exc}",
                    "meta": {},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    allowed = [t.strip() for t in args.allowed_tables.split(",") if t.strip()]
    conn_params = load_connection_params_from_env()

    with PostgreSQLSkill(conn_params, allowed_tables=allowed, max_rows=args.max_rows) as skill:
        if skill.connection is None:
            print(
                json.dumps(
                    {
                        "success": False,
                        "data": [],
                        "count": 0,
                        "error": "database connection failed (check PG* env or psycopg2 install)",
                        "meta": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

        result = skill.query_safe(args.query, params)
        print(result.to_json())
        return 0 if result.success else 3


if __name__ == "__main__":
    raise SystemExit(main())
