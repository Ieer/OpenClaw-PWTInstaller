# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No heavy generation, no side effects, no launching experiments.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Heartbeat Schedule

- **心跳间隔**：每天一次
- **配置文件**：`state/heartbeat-config.json`

## Silent Hours

- **静默时段（北京时间 18:00–23:00 / UTC 10:00–15:00）**
- 静默时段内：心跳检查仍运行，但不发送响应（只更新内部状态）
- 如需跳过当前心跳但保留检查：返回 `HEARTBEAT_OK`

## Every Heartbeat

- Check active experiment task queue and stale items.
- Check `state/` for blocked hypotheses waiting for user input.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Compile pending funnel anomalies into a short checklist note.
- Mark any externally visible change requests as Review-required.

## Weekly (once)

- Write growth learnings to `memory/lessons.md`.
- Roll stable strategy context into `MEMORY.md` index links.
