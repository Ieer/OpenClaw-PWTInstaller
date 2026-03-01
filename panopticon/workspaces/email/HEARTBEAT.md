# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No heavy generation, no side effects, no sending.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

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
