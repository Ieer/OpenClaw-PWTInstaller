````skill
---
name: knowledge-eval
description: "Shared Mission Control knowledge evaluation skill for Panopticon agents. Use when Claude needs to assess a task against the central knowledge system, build a standardized POST /v1/knowledge/resolve request, apply agent_slug/risk defaults, and return a normalized evaluation summary with evidence and constraints."
license: Proprietary. Inherit repository-level license unless overridden
---

# Overview

This skill standardizes how the 8 Panopticon agents call Mission Control knowledge evaluation.

## knowledge-eval Workflow

1. Identify whether the task needs a formal knowledge-backed evaluation.
2. Build a standardized `POST /v1/knowledge/resolve` request.
3. Fill `task`, `agent_slug`, and `risk_level`.
4. Optionally add `tags`, `source_type`, `retrieval_mode`, `ranking_profile`, and thresholds.
5. Execute [`scripts/knowledge_eval.py`](scripts/knowledge_eval.py).
6. Return both:
   - raw resolve response
   - normalized summary: status, top evidence, constraints, recommended action

## Use When

- 需要先做资料评估再给出正式判断
- 需要统一 8 个 agent 的知识调用方式
- 需要根据 `agent_slug` 和 `risk_level` 走 Mission Control 治理链路
- 需要把返回结果整理成可复用的“结论 + 依据 + 限制”模板

## Do Not Use When

- 纯闲聊或纯格式整理
- 仅需要搜索候选资料而不需要正式评估
- 需要写入 validation / policy / source import 后台数据

## Run

```bash
cd panopticon/global-skills/knowledge-eval
python3 scripts/knowledge_eval.py \
  --task "评估本周增长实验是否应继续投放" \
  --agent-slug growth \
  --risk-level high \
  --tags experiment,funnel
```

Environment variables:

- `AGENT_SLUG`
- `MISSION_CONTROL_API_URL` or `KNOWLEDGE_RESOLVE_URL`
- `EVENT_HTTP_URL` as API base fallback
- `EVENT_HTTP_TOKEN`
- optional `KNOWLEDGE_EVAL_DEFAULT_RISK`
- optional `KNOWLEDGE_EVAL_DEFAULT_LIMIT`

## Outputs

- Standard JSON payload:
  - `ok`
  - `request`
  - `summary`
  - `raw`
  - `error`

## Notes

- The client summary does not replace backend validation policy.
- Final trust decisions still belong to Mission Control `resolve`.
- This skill is the preferred first implementation layer; wrapper automation can be added later.

## Version

- Template-Version: 0.1.0
- Last-Updated: 2026-04-04

````