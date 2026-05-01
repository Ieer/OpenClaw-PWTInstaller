# AGENTS.md - {{AGENT_SLUG}}

## Every Session

1. Read `SOUL.md`
2. Read `USER.md`
3. Read `memory/YYYY-MM-DD.md` (today + yesterday)
4. In main session, also read `MEMORY.md`

## Memory Layers

- `MEMORY.md`：长期索引
- `memory/projects.md`：项目状态
- `memory/infra.md`：环境与集成
- `memory/lessons.md`：经验复盘
- `memory/YYYY-MM-DD.md`：当日日志

## memorySearch Usage

- Search first, then write.
- Prefer semantic recall when available.
- Fallback to keyword scan over `memory/`.
- Keep evidence paths in outputs.

## Workspace Folder Hygiene

Root stays clean. Create ordinary files inside a classified folder, not beside `AGENTS.md`.

Allowed root files:

- `AGENTS.md`, `SOUL.md`, `USER.md`, `IDENTITY.md`, `HEARTBEAT.md`, `TOOLS.md`, `MEMORY.md`, `README.md`, `RUNTIME_POLICY.md`

Allowed root directories:

- Contract: `inbox/`, `outbox/`, `artifacts/`, `state/`, `sources/`, `memory/`, `skills/`
- Classification: `docs/`, `media/`, `exports/`, `scripts/`, `runtime-assets/`, `staging/`, `archive/`, `.trash/`
- System: `.openclaw/`, `.claude/`, `.release-state/`

Default destinations:

- `docs/` — durable drafts, SOPs, Mermaid sources, long-form markdown.
- `media/` — images, screenshots, thumbnails, rendered diagrams, audio/video intermediates.
- `exports/` — final PDFs, PPTX, HTML, ZIPs, and human-facing deliverables.
- `scripts/` — one-off helpers and generators; promote reusable tools to `skills/` later.
- `runtime-assets/` — fonts, OCR data, templates, offline packages, required local runtime assets.
- `staging/` — temporary or uncertain work in progress.
- `archive/` — completed historical work and old versions that still matter.
- `.trash/` — recoverable cleanup candidates; never use destructive deletion first.

If unsure, write to `staging/<date-or-task>/` and mention the location in the task closeout.

## Skill Extension Rule

- Trigger
- Steps
- Output (artifacts/sources/state)
- Review Gate for side effects

## Model Tier Routing (Policy-Only)

- `small`：分类/抽取/格式化
- `medium`：分析/规划/综合
- `large`：长文/复杂推理/高风险草案

Use the smallest tier that can safely finish the task.

## Heartbeats - I/O-Only

- No heavy generation
- No external side effects
- If nothing actionable: `HEARTBEAT_OK`
