# Mission Control Overview

This document describes the current Mission Control control plane in this repository and the remaining optional extension path. The active runtime track is the **8-agent Personal Panopticon**: `nox`, `metrics`, `email`, `growth`, `trades`, `health`, `writing`, and `personal`.

For the detailed engineering playbook, see:

- [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md)
- [mission-control-personal-panopticon-zh-hant.md](mission-control-personal-panopticon-zh-hant.md)
- [../panopticon/README.md](../panopticon/README.md)

## Current Status

Mission Control is no longer a mocked UI-only prototype. The repository currently includes a runnable control plane with:

- Dash UI in [../MissionControl/app.py](../MissionControl/app.py)
- FastAPI API in [../mission_control_api/app/main.py](../mission_control_api/app/main.py)
- PostgreSQL persistence for tasks, comments, events, skills mappings, and knowledge data
- Redis Streams for realtime event fanout
- WebSocket feed at `/ws/events`
- same-origin Chat proxy through the Mission Control Gateway at `/chat/<agent>/`
- observability endpoints for readiness, event/task metrics, and container health
- skills inventory, runtime config, drift detection, and mapping APIs
- knowledge source import, chunking, validation policy, resolve, audit, and feedback APIs
- voice command adapter for prefixed ASR commands
- Panopticon generation, validation, backup, upgrade, rollback, and health-check scripts

The generated compose stack is defined by [../panopticon/agents.manifest.yaml](../panopticon/agents.manifest.yaml) and [../panopticon/docker-compose.panopticon.yml](../panopticon/docker-compose.panopticon.yml). The compose file is generated and should not be treated as the long-term source of truth.

## Architecture

- **Control Plane**: Dash UI, FastAPI API, gateway, Postgres, Redis.
- **Data Plane**: one isolated OpenClaw container per enabled agent.
- **Realtime Transport**: Redis Streams plus `/ws/events`; the UI uses WebSocket events as the primary invalidation signal and polling as a fallback.
- **Task Store**: PostgreSQL tables for tasks, comments, and append-only events.
- **Knowledge Store**: PostgreSQL-backed knowledge sources, units, validation policies, resolve audits, feedback, lifecycle events, and optional embeddings.
- **Gateway**: same-origin entry point for the dashboard and per-agent chat.

## Primary User Paths

1. Open Mission Control at `http://127.0.0.1:18920/` or the configured LAN gateway URL.
2. Review the agent roster, task queue, observability cards, and live feed.
3. Open `/chat/<agent>/` through the same-origin gateway for an individual agent session.
4. Create, claim, update, review, or hand off tasks through the API or voice command adapter.
5. Review skills inventory, mapping drift, runtime config, and restart hints before applying changes.
6. Import and resolve knowledge units with validation policy and audit trails.

## Runtime Components

### Mission Control UI

The Dash UI renders the agent roster, mission queue, live feed, observability cards, skills/config panels, embedded chat modal, and voice overlay. It now uses WebSocket event invalidation for board/feed/roster refreshes and keeps polling as a fallback when WebSocket is unavailable.

### Mission Control API

The FastAPI service provides tasks, comments, events, feed, observability, agent catalog, agent control forwarding, chat proxy compatibility, skills governance, voice command parsing, and knowledge APIs. `/ready` checks Redis and Postgres; `/v1/observability/container-health` probes compose, port, and HTTP signals with bounded concurrency.

### Mission Control Gateway

The gateway is the preferred browser entry point. It keeps the dashboard and chat under the same origin, which avoids most CORS and token-injection problems. LAN access still requires exact Origin allowlisting in each agent's OpenClaw gateway config.

### Agents

The current roster is the 8-agent Personal Panopticon. Each agent has its own home directory, workspace, environment file, gateway port, bridge port, token, and skills boundary.

## Security Model

- `MC_AUTH_TOKEN` enables bearer-token auth for Mission Control API and WebSocket access.
- Agent gateway tokens are generated and rotated through Panopticon tooling.
- Direct agent links are disabled by default; same-origin `/chat/<agent>/` is preferred.
- The optional `mission-control-agent-controller` is high risk because it mounts `docker.sock`; it is disabled by default and requires explicit risk acceptance plus a long random token.
- High-risk personal, health, trading, and infrastructure actions should go through review gates.

## Observability and Health

Mission Control exposes lightweight and deeper health surfaces:

- `/health`: process liveness.
- `/ready`: Redis and Postgres readiness.
- `/v1/observability/summary`: recent request/error/event/task/heartbeat metrics.
- `/v1/observability/container-health`: compose dependency checks plus bounded-concurrency port and HTTP probes.
- `/v1/feed-lite` and `/ws/events`: dashboard feed and realtime UI invalidation.

Operational scripts such as [../panopticon/tools/check_panopticon_services.sh](../panopticon/tools/check_panopticon_services.sh) and [../panopticon/tools/check_agent_endpoints.sh](../panopticon/tools/check_agent_endpoints.sh) are the recommended smoke checks after changes.

## Optional Extension Path

The earlier 10-agent architecture remains useful as a design reference, but it is not the current default stack. Potential future extensions include:

- expanding the roster beyond the 8 personal agents
- adding stronger task assignment queues and consumer-group recovery semantics
- adding richer memory retrieval, embedding backends, or Qdrant integration
- adding Slack, Discord, Feishu, or mobile notifications
- adding stricter role-based access control for multi-user operation
- moving UI smoke checks into a browser-based regression suite

Convex is not required for the current implementation. The current task and event store is PostgreSQL plus Redis Streams.

## Verification Checklist

- `python -m pytest mission_control_api/tests`
- `bash panopticon/tools/check_panopticon_services.sh`
- `bash panopticon/tools/check_agent_endpoints.sh`
- open `http://127.0.0.1:18920/`
- open `http://127.0.0.1:18920/chat/nox/`
- for LAN access, verify `http://<gateway-lan-ip>:18920/chat/<agent>/` and exact Origin allowlisting

## Known Boundaries

- The dashboard and API are optimized for a trusted local or LAN deployment unless stronger auth, HTTPS, or private networking is added.
- WebSocket live updates improve perceived latency but are not the durable source of truth; PostgreSQL and Redis-backed events remain authoritative.
- Voice command execution intentionally requires prefixes by default to reduce accidental control-plane actions.
- Agent controller operations should remain disabled unless remote container control is explicitly needed.
