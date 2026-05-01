# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No roadmap generation, no heavy planning loops.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Schedule

- 频率：每天一次
- 时间：北京时间 21:00（UTC 13:00）

## Every Heartbeat

- Check product-ops task queue freshness and blocked cards.
- **基础设施自愈：** 使用 `skills/self-heal/` 的 registry-driven runner；默认只诊断，不自动执行 L2/L3/L4 修复。
  - 快速诊断：`python3 skills/self-heal/scripts/self_heal_runner.py diagnose --max-level L1 --exit-zero`
  - 首批 registry items 覆盖：Python 包、Rokid 插件、ByPy token、wjx-cli、state queue、workspace contract、Mission Control/API endpoint、release dry-run/rollback readiness。
  - L2 容器/服务重启、L3 token/外部服务恢复、L4 release/rollback 执行必须走 Review Gate。
- Check `state/` for pending handoff/review gates.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Compile one lightweight operations pulse: risks, blockers, dependencies.
- Mark any external commitment/release-impact action as Review-required.

## Weekly (once)

- Summarize roadmap lessons into `memory/lessons.md`.
- Promote durable operating context into `MEMORY.md` index links.
