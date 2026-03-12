# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No diagnosis generation, no intervention actions.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## 心跳间隔

- 每24小时1次
- 静默时段（05:00–10:00 UTC）内仍按规则响应

## 静默时段

- 每日05:00–10:00为静默时段
- 静默时段内仅执行 I/O 检查；不生成任何诊断或干预建议
- 在静默时段内，若无待处理事项，应返回 `HEARTBEAT_OK`

## Every Heartbeat

- Check routine tracker status (sleep/training/recovery logs present or missing).
- Check `state/` for pending Review decisions on high-risk suggestions.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Produce a lightweight compliance check: missing logs, irregular spikes, open questions.
- Mark all high-risk recommendations as Review-only.

## Weekly (once)

- Summarize patterns into `memory/lessons.md`.
- Update durable habits and constraints in `MEMORY.md` via index links.
