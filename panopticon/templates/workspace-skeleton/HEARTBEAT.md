# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only.
- Follow this file only.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Every Heartbeat

- Check queue freshness and blockers in `state/`.
- Refresh `memory/heartbeat-state.json`.

## Daily (once)

- Emit lightweight pending-items summary.
- Mark Review-required items.

## Weekly (once)

- Summarize reusable lessons into `memory/lessons.md`.
- Promote stable context into `MEMORY.md`.
