# Mission Control Implementation Plan

This doc describes a general Mission Control architecture and uses a **10-agent example roster** as a reference. This repository also includes a separate **8-agent personal configuration** ("Personal Panopticon") optimized for one-person workflows:

- [docs/my_mission_control.md](docs/my_mission_control.md) (Traditional Chinese, complete record)
- [docs/unmanned-company-playbook-zh-cn.md](docs/unmanned-company-playbook-zh-cn.md) (Simplified Chinese, engineering playbook)

Implementation status note:

- The Dash UI prototype exists in [MissionControl/app.py](MissionControl/app.py) and currently uses mocked data.
- API/Redis Streams/WebSocket/Convex/vector store integration are described as target components and may require additional implementation work.

## Goals

Build a multi-agent "Mission Control" system on top of OpenClaw where each agent runs in an isolated container, shares a central task system, and reports real-time activity. The system prioritizes cost control, auditability, and collaboration.

## Architecture Overview

- **Control Plane**: Mission Control web app + API + realtime transport.
- **Data Plane**: 10 OpenClaw agents, each in a dedicated container.
- **Async Bus**: Redis Streams for task assignment and event fanout.
- **Task Store**: Convex for realtime board, comments, and activity feed.
- **Memory**: Vector store (pgvector or Qdrant) for semantic recall.

## Component Breakdown

### 1) Agents (OpenClaw containers)

- One container per agent role (Jarvis, Shuri, Fury, Vision, Loki, Quill, Wanda, Pepper, Friday, Wong).
- Each container has its own config and secrets and a scoped toolset.
- Agents expose REST endpoints on port 18789 for task execution and health.

### 2) Mission Control Web

- **UI**: Kanban board + live activity feed + agent roster.
- **Backend**: Task state machine, assignment logic, audit log.
- **Realtime**: WebSocket channel for live events and status updates.

### 3) Task Model (Core Schema)

- **Task**: title, status, assignee, priority, tags, created_at, due_at.
- **Run**: task_id, agent_id, status, logs, started_at, ended_at.
- **Comment**: task_id, author, body, created_at.
- **Artifact**: task_id, type, uri, summary, embeddings.
- **Event**: append-only action log for auditability.

### 4) Communication Flow

- **REST**: Mission Control assigns tasks to agents; agents report artifacts and run status.
- **WebSocket**: Agents push live status/logs to Mission Control; UI receives realtime updates.
- **Redis Streams**: Guarantees task delivery and replays on failure.

## Heartbeat and Cost Control

- Each agent runs a lightweight heartbeat every 13-17 minutes (jittered).
- Heartbeat checks for queued tasks without invoking full LLM.
- Only when a task is found does the agent load full context and run inference.

## Security and Isolation

- Per-agent secrets and tool permissions.
- Read/write restrictions on mounted workspaces.
- All actions recorded in the Event log.

## Step-by-Step Build Plan

1. **Spin up 2-3 agents** to validate task assignment and reporting.
2. **Stand up Mission Control UI** with mocked data (Dash or Next.js).
3. **Implement task state machine** (Queued -> Assigned -> InProgress -> Review -> Done).
4. **Integrate Redis Streams** for assignment and recovery.
5. **Enable WebSocket live updates** from agent wrappers.
6. **Expand to 10 agents** and add memory/vector search.
7. **Add notifications** (Slack/Discord/Feishu) and audit dashboards.

## Risks and Mitigations

- **API limitations**: If OpenClaw lacks needed REST endpoints, use a wrapper skill to POST results to Mission Control.
- **Log volume**: Stream logs with backpressure; drop non-critical logs on overload.
- **Task duplication**: Enforce lock + idempotency for task claims.

## Verification Checklist

- Tasks can be created, assigned, run, and reviewed end-to-end.
- Heartbeat does not trigger LLM calls when idle.
- Realtime feed updates within 1s of agent events.
- Agent isolation prevents cross-agent access.

## Next Steps

- Confirm preferred vector store (pgvector or Qdrant).
- Decide initial backend stack for Mission Control API.
- Define 10 agent prompt profiles and tool permissions.
