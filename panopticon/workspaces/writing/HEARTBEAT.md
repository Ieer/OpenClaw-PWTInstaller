# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No long-form drafting or publishing actions.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Every Heartbeat

- Check writing queue freshness and missing-source blockers.
- Check `state/` for drafts waiting on Review.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Output a short draft pipeline note (outline/draft/review gaps).
- Mark external publication tasks as Review-required.

## Weekly (once)

- Summarize writing lessons into `memory/lessons.md`.
- Promote durable style constraints into `MEMORY.md` index links.
