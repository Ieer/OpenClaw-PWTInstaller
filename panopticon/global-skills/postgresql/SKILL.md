````skill
---
name: postgresql
description: "Safe PostgreSQL read-only querying skill for AI agents. Use when Claude needs to query PostgreSQL for reports, analytics, and operational insights with strict safety boundaries (SELECT-only, parameterized queries, table allowlist, row limits)."
license: Proprietary. Inherit repository-level license unless overridden
---

# Overview

This skill enables AI to query PostgreSQL safely under strict guardrails.

## postgresql Workflow

1. [Understand request intent](#intent-and-boundary).
2. **MANDATORY - READ ENTIRE FILE**: Read [`security.md`](security.md) fully before querying production-like databases.
3. Convert user intent to a **read-only** SQL plan:
   - SELECT / WITH ... SELECT only
   - Parameterized placeholders (`%s`) only for dynamic values
   - No dynamic table names unless from allowlist
4. Execute query via [`scripts/postgresql_skill.py`](scripts/postgresql_skill.py):
   - SQL safety validation
   - table allowlist check (if configured)
   - result row limit enforcement
5. Return compact JSON results and concise interpretation.

## Intent and Boundary

### Allowed
- Read-only SQL (`SELECT`, `WITH ... SELECT`)
- Parameterized filters
- Aggregation, grouping, sorting
- Optional table allowlist restrictions

### Forbidden
- Any write/DDL statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, etc.)
- Multiple statements in one call
- Unsafe dynamic SQL composition

## Use Cases

- 查询上周新增用户数
- 查询活动参与数据与分布
- 查询指标异常（错误率、转化率）
- 导出小规模数据用于后续分析

## NL2SQL Templates

- 快速映射文件：[`nl2sql_templates.json`](nl2sql_templates.json)
- 内容包含 20 条常见业务问句 → 安全 SQL 模板（参数化、SELECT-only）
- 使用方式：先匹配 `intent` / `question_examples`，再按 `params_order` 填参数执行

## Run

```bash
cd panopticon/global-skills/postgresql
python3 scripts/postgresql_skill.py \
  --query "SELECT now() AS ts" \
  --params "[]"
```

Environment variables:

- `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
- optional `PG_ALLOWED_TABLES` (comma-separated)
- optional `PG_MAX_ROWS` (default 1000)

## Inputs

- Natural language request
- SQL template with `%s` placeholders
- parameters tuple/list
- optional table allowlist and row-limit policy

## Outputs

- Standard JSON payload:
  - `success`: bool
  - `data`: list[dict]
  - `count`: int
  - `error`: str (when failed)
  - `meta`: execution metadata

## Safety

- Enforce read-only SQL checks before execution
- Use parameterized queries only
- Restrict accessible tables by allowlist
- Enforce max row limit (append LIMIT when absent)
- Avoid leaking credentials or full stack traces

## Version

- Template-Version: 1.0
- Last-Updated: 2026-02-26

````
