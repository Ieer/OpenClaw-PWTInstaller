# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No trading actions, no execution suggestions.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Every Heartbeat

- Check market-watch queue freshness and source availability.
- Check `state/` for unresolved assumptions/risk flags.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Produce a short watchlist-risk note with explicit uncertainty tags.
- Mark all strategy decisions as Review-required.

## Weekly (once)

- Distill repeated risk lessons into `memory/lessons.md`.
- Promote durable thesis/constraint notes into `MEMORY.md` index links.
