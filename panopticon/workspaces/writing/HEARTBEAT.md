# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No long-form drafting or publishing actions.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Silent Hours

- Daily quiet period: 18:00–23:00 (UTC)
- During silent hours: skip all heartbeat tasks, reply immediately with `HEARTBEAT_OK`

## Heartbeat Frequency

- Daily heartbeat (once per day)

## Every Heartbeat

- Check writing queue freshness and missing-source blockers.
- Check `state/` for drafts waiting on Review.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once, during heartbeat)

- Output a short draft pipeline note (outline/draft/review gaps).
- Mark external publication tasks as Review-required.

## Weekly (once, during heartbeat)

- Summarize writing lessons into `memory/lessons.md`.
- Promote durable style constraints into `MEMORY.md` index links.
