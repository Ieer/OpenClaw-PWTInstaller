# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No heavy generation, no side effects, no launching experiments.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

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
