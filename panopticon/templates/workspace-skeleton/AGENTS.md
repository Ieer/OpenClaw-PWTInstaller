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
