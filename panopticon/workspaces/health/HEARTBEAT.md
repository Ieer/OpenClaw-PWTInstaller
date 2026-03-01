# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No diagnosis generation, no intervention actions.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

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
