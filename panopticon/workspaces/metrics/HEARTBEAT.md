# HEARTBEAT.md

## Rule Zero

- Heartbeat is I/O-only. No deep analysis jobs, no report drafting.
- Follow this file only. Do not infer extra tasks from old chats.
- If nothing requires action, reply exactly: `HEARTBEAT_OK`.

## Schedule

- Heartbeat interval: Once daily
- Silent hours: 18:00–23:00 daily (Asia/Shanghai timezone)
- During silent hours, skip all heartbeat checks and reply `HEARTBEAT_OK` immediately

## Every Heartbeat

- Check metric feed freshness and missing-data signals.
- Check anomaly queue and unresolved investigation markers in `state/`.
- Refresh `memory/heartbeat-state.json` timestamps.

## Daily (once)

- Emit a short risk note: data gaps, definition drift, potential Goodhart signals.
- Mark publish/external-share tasks as Review-required.

## Weekly (once)

- Distill recurring pitfalls into `memory/lessons.md`.
- Promote stable metric definitions into `MEMORY.md` index links.
