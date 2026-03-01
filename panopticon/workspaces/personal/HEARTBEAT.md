# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No autonomous purchases/cancellations/sends.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Every Heartbeat

- Check pending personal admin items and due-date drift.
- Check `state/` for blocked to-dos that need user confirmation.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Generate a short priorities note (today/this week).
- Mark irreversible actions as Review-required.

## Weekly (once)

- Summarize recurring friction points into `memory/lessons.md`.
- Promote stable routines/preferences into `MEMORY.md` index links.
