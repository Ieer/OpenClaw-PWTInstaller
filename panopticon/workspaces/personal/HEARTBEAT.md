# HEARTBEAT.md

## Heartbeat Interval

- **Frequency:** 每天 6:00 UTC，每天一次
- **Last updated:** 2026-03-21

## Rule Zero

- Heartbeat is I/O-only. No autonomous purchases/cancellations/sends.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Daily Heartbeat（每天 6:00 UTC）

- Check pending personal admin items and due-date drift.
- Check `state/` for blocked to-dos that need user confirmation.
- Refresh `memory/heartbeat-state.json` timestamps.
- Generate a short priorities note (today/this week).
- Mark irreversible actions as Review-required.

## Weekly (once)

- Summarize recurring friction points into `memory/lessons.md`.
- Promote stable routines/preferences into `MEMORY.md` index links.
