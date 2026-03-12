# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No trading actions, no execution suggestions.
- Follow this file only. Do not infer extra tasks from prior chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Silent Hours (UTC)

- 10:00–15:00 UTC daily (Beijing 18:00–23:00): Skip all heartbeat checks and routine tasks
- Outside silent hours: Proceed with normal heartbeat checks

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
