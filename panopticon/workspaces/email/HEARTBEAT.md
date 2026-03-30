# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No heavy generation, no side effects, no sending.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Heartbeat Schedule

- **Frequency:** Once per day
- **Scheduled time:** 7:00 AM (UTC+8/Asia-Shanghai) ≈ 23:00 UTC (previous day)
- Run full checks once daily at scheduled time; other heartbeat requests during same day return `HEARTBEAT_OK`

## Silent Hours (Quiet Period)

- **Silent window:** Daily 13:00–16:00 UTC
- During silent hours: Always reply `HEARTBEAT_OK` without any checks
- Skip all inbox, state, and file operations during this window

## Every Heartbeat

- Check inbox queue status and unread count snapshot.
- Check whether any task is waiting in `state/` with blocker notes.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Build a short "needs-reply" list in `outbox/` draft notes.
- Flag items that require Review (external send, commitments, sensitive data).

## Weekly (once)

- Summarize repeated email patterns into `memory/lessons.md`.
- Promote durable preferences into `MEMORY.md` index links.
