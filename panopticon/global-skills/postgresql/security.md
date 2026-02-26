# PostgreSQL Skill Security Guide

This document defines mandatory controls for AI-driven PostgreSQL querying.

## 1) Principle: Read-Only by Default

- Only allow `SELECT` and `WITH ... SELECT`.
- Block write/DDL/admin keywords:
  - `INSERT`, `UPDATE`, `DELETE`, `UPSERT`, `MERGE`
  - `DROP`, `ALTER`, `CREATE`, `TRUNCATE`
  - `GRANT`, `REVOKE`, `COPY`, `DO`, `CALL`, `VACUUM`, `ANALYZE`, `REFRESH`
- Reject multi-statement SQL (`;`-chaining).

## 2) DB Privilege Isolation

Recommended DB role:

```sql
CREATE ROLE readonly_user WITH LOGIN PASSWORD 'replace_me';
GRANT CONNECT ON DATABASE app_db TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;
```

Never use superuser credentials in AI runtime.

## 3) Parameterization Rules

- Dynamic values must be placeholders (`%s`) + `params`.
- Never interpolate user text directly into SQL string.
- Table names cannot come from raw user input; if dynamic, must pass allowlist + identifier-safe handling.

## 4) Data Exfiltration Controls

- Enforce maximum row count (`PG_MAX_ROWS`, default 1000).
- Avoid returning sensitive columns by default (e.g. password hash, tokens).
- Prefer aggregated metrics over raw records when possible.

## 5) Observability

Record metadata (without secrets):
- execution timestamp
- normalized query fingerprint/hash
- row count returned
- blocked/allowed decision reason

## 6) Failure Behavior

- On any safety violation: fail closed (`success=false`) with concise reason.
- Do not execute partial SQL.
- Do not leak connection strings, passwords, or stack traces to users.

## 7) Operator Checklist

- [ ] Runtime user has read-only DB privileges
- [ ] `PG_ALLOWED_TABLES` configured for production
- [ ] `PG_MAX_ROWS` set to business-safe threshold
- [ ] Query logs scrub sensitive values
- [ ] Unit tests for SQL guardrails pass
