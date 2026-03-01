# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No roadmap generation, no heavy planning loops.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Every Heartbeat

- Check product-ops task queue freshness and blocked cards.
- Check `state/` for pending handoff/review gates.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Compile one lightweight operations pulse: risks, blockers, dependencies.
- Mark any external commitment/release-impact action as Review-required.

## Weekly (once)

- Summarize roadmap lessons into `memory/lessons.md`.
- Promote durable operating context into `MEMORY.md` index links.
