# 用 OpenClaw 组建 8-Agent 虚拟 AI 团队：无人公司工程落地手册（简中）

⚠️ 免责声明：本文所有信息仅用于学习与工程讨论。请在充分了解安全风险、合规要求与成本约束后谨慎使用。任何涉及生产系统、真实资金、真实用户数据的自动化操作必须经过人工审核。

本手册把“Mission Control + 多智能体团队”的叙事内容改写为可执行的工程落地方案，统一以 **8-agent Personal Panopticon**（nox/metrics/email/growth/trades/health/writing/personal）为目标配置。

相关文件（本 repo）：

- 繁中完整备案（更细、偏设计与治理）：[docs/my_mission_control.md](docs/my_mission_control.md)
- 通用 Mission Control 设计草案（英文）：[docs/mission-control.md](docs/mission-control.md)
- Dash UI 原型（当前为 mock data）：[MissionControl/app.py](MissionControl/app.py)
- OpenClaw 配置参考（含 security / scheduler / channels）：[examples/config.example.yaml](examples/config.example.yaml)
- CN-IM Docker 模板（env→openclaw.json）：[src/OpenClaw-Docker-CN-IM/README.md](src/OpenClaw-Docker-CN-IM/README.md)
- 8-service Panopticon Compose（已落地）：[panopticon/docker-compose.panopticon.yml](panopticon/docker-compose.panopticon.yml)

---

## 0. 目标架构 vs 当前仓库落地状态（务必读）

### 目标架构（本文描述的“核心组件”）

- Control plane：Dash UI + API（建议 FastAPI）+ WebSocket（实时 feed）
- Data plane：8 个 OpenClaw agent 容器（每 agent 独立隔离）
- Async bus：Redis Streams（任务分发与事件可重放）
- Task store：Convex（实时看板/评论/动态，或同类替代）
- Memory：pgvector 或 Qdrant（可选，但本文仍按“核心能力”描述）

### 当前仓库已落地

- Dash UI 原型已存在，但目前是静态 mock 数据展示：[MissionControl/app.py](MissionControl/app.py)
- Redis/Convex/向量库/WS/任务一致性等属于“设计与待实现”范畴（本文会按工程手册写清楚接口与约束，但不声称已实现）。

---

## 1. 核心原则（工程约束）

1. **一 agent 一容器**：隔离配置、缓存、技能与权限，避免“会话污染”。

1. **可靠性与实时感分离**：

	- 可靠：REST + Redis Streams（任务一致性、可重放、幂等）
	- 实时：WebSocket（live feed，可断线降级，不影响任务完成）

1. **成本控制优先**：

	- Heartbeat 采用 13–17 分钟抖动
	- Heartbeat 禁止触发 LLM（只做 I/O）
	- 只有 claim 到任务才允许推理

1. **审计优先**：每次任务必须 artifact 化（JSON + Markdown + sources 索引），并写入事件流。

---

## 1.1 一键启动（8-service compose 模板）

本 repo 已提供 8 个 agent 的 compose 与 per-agent env_file 模板（对齐 CN-IM 的 env→openclaw.json 生成方式）：

- Compose： [panopticon/docker-compose.panopticon.yml](panopticon/docker-compose.panopticon.yml)
- 使用说明： [panopticon/README.md](panopticon/README.md)
- env 模板目录： [panopticon/env/](panopticon/env/)

---

## 2. 8 个 agent 责任边界（责任＝数据边界＝权限边界）

- nox：产品运营与 roadmap 建议（产品数据 + 代码/变更对照 → “该做什么”）
- metrics：指标/归因/异常检测（含 Goodhart guardrail）
- email：收件箱分类、草拟回复、追踪待回（仅允许邮件相关 API/IMAP/SMTP）
- growth：实验设计、文案、漏斗（仅允许 growth workspace 与分析读）
- trades：晨报/论点追踪/资料整合（严格引用与假设，禁止“凭空交易结论”）
- health：睡眠/训练/恢复建议（不做高风险自动执行）
- writing：长文/文档/内容产出（强制引用 artifacts，不凭空下结论）
- personal：订阅/票据/待办/行程（高风险动作默认 Review）

---

## 3. Workspace 工作契约（目录结构与产物规范）

每个 workspace（例如 ~/nox）建议固定结构：

- inbox/：新任务与外部输入
- outbox/：交付物
- artifacts/：任务产物（可检索、可回放）
- state/：checkpoint、游标、上次处理位置
- sources/：原始资料快照与引用索引

每次任务最少产出：

- artifacts/<task_id>/artifact.json：结构化摘要（结论、假设、风险、下一步、引用）
- artifacts/<task_id>/artifact.md：可读版本
- sources/<task_id>/：引用索引（必要时附快照）

---

## 4. 通讯与一致性：REST + Redis Streams + WS

### 4.1 任务分配（可靠）

- Mission Control 写入 Redis Stream：`task.assign`
- 事件追踪写入 Redis Stream：`event.log`

### 4.2 任务领取（低成本）

- agent heartbeats 只做：拉取 stream → 尝试 claim lock → 更新 last_seen
- 成功 claim 才进入推理阶段

### 4.3 结果回传（可靠）

- agent 将 artifacts 通过 REST 上传到 Mission Control
- 同时把关键状态变更写入 `event.log`（append-only）

### 4.4 实时呈现（即时但可降级）

- agent wrapper 将进度/摘要日志通过 WS 推到 live feed
- WS 断线时：仅缺实时感，不影响任务一致性

---

## 5. Heartbeat（13–17 分钟抖动）与成本控制

约束（必须满足）：

- Heartbeat 不得触发 LLM
- Heartbeat 仅做 I/O：查任务、回报 alive、写 checkpoint

推荐 checklist（示例）：

- Scan inbox（仅元数据，不做全文推理）
- Check calendar 2h（只读）
- Pull task.assign（按优先级筛选）
- If quiet 8h：写一条“轻量 check-in”（不触发推理）

---

## 6. 8-agent 配置矩阵（推荐默认）

说明：这里用“模型层级”表达（small/medium/large），可映射到 CN-IM 模板的 `MODEL_ID / CONTEXT_WINDOW / MAX_TOKENS`。

| Agent | Workspace | 模型层级 | CONTEXT_WINDOW | MAX_TOKENS | Browser | Shell | Skills（global） | Skills（workspace） | 留存策略 |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| nox | ~/nox | medium | 64k–128k | 2k–4k | 只读 | 受限 | product-core, handoff, artifact | nox/* | artifacts 90d；sources 30d |
| metrics | ~/metrics | medium | 64k–128k | 2k–4k | 只读 | 受限 | metrics-core, anomaly, goodhart | metrics/* | artifacts 180d；sources 90d |
| email | ~/email | small | 16k–64k | 1k–2k | 否 | 否 | email-core, redact, artifact | email/* | artifacts 30–90d；sources 7–30d |
| growth | ~/growth | medium | 64k–128k | 2k–4k | 只读 | 受限 | growth-core, experiment | growth/* | artifacts 180d；sources 30–90d |
| trades | ~/trades | medium | 64k–128k | 1k–2k | 只读 | 否 | trades-core, citations, risk | trades/* | artifacts 365d；sources 180d |
| health | ~/health | small | 16k–64k | 1k–2k | 否 | 否 | health-core, safety, artifact | health/* | artifacts 180d；sources 30d |
| writing | ~/writing | large | 128k+ | 4k–8k | 只读 | 受限 | writing-core, outline, cite | writing/* | artifacts 365d；sources 180d |
| personal | ~/personal | small | 16k–64k | 1k–2k | 可选 | 否 | personal-core, review-gate, redact | personal/* | artifacts 180d；sources 30–90d |

Browser/Shell 权限建议：

- 只读 browser：仅允许白名单域名抓取并落到 sources/；禁止任意上传。
- 受限 shell：仅允许 workspace 内白名单命令；禁止系统管理、网络扫描、任意外联。

---

## 7. Skills 治理：global + workspace 双层

目标：通用能力与角色能力解耦，可审计、可灰度、可回退。

### 7.1 Global skills（平台通用能力）

- 不含业务逻辑：artifact、handoff、redaction、事件上报、格式检查
- 每个 agent 通过 allowlist 限定可用 skills

### 7.2 Workspace skills（角色特化）

- 每个 workspace 自己维护（`nox/*`、`metrics/*`…）
- 明确 I/O：可读哪些目录、可写哪些目录、可用哪些外部 API

### 7.3 装载顺序（推荐）

- 先 global 再 workspace；同名冲突以 workspace 覆盖（但需要审计/Review）

---

## 8. 基于 CN-IM 模板：多 agent 差异化所需新增字段

CN-IM 模板已有字段（可沿用）：
- `MODEL_ID / BASE_URL / API_KEY / API_PROTOCOL`
- `CONTEXT_WINDOW / MAX_TOKENS`
- `WORKSPACE`
- `OPENCLAW_DATA_DIR`
- `OPENCLAW_GATEWAY_*`

为支持多 agent 与 Mission Control 整合，建议补齐：
- `AGENT_SLUG`：nox/metrics/email/...
- `AGENT_HOST_PORT`：host 映射端口（容器内仍使用 18789）
- `OPENCLAW_HOME_DIR`：容器内 OpenClaw home（如 /root/.openclaw）
- `WORKSPACE_DIR`：容器内挂载点（如 /workspace）
- `GLOBAL_SKILLS_DIR`：如 /skills/global
- `WORKSPACE_SKILLS_DIR`：如 /workspace/skills
- `SKILLS_ALLOWLIST`：允许加载的 skills 清单
- `ENABLE_BROWSER` / `ENABLE_SHELL`
- `REDACTION_MODE`：off/basic/strict
- `EVENT_HTTP_URL` / `EVENT_WS_URL`
- `HEARTBEAT_MINUTES_MIN` / `HEARTBEAT_MINUTES_MAX`
- `RETENTION_ARTIFACT_DAYS` / `RETENTION_SOURCES_DAYS`

注意：CN-IM 的 init 逻辑通常是“openclaw.json 不存在才生成”，多 agent 场景务必保证每个容器独立的 OpenClaw home/数据目录，避免共用导致污染。

---

## 9. 安全护栏（必须默认开启）

- trades / health / personal：任何高风险动作默认进入 Review，不自动执行
- 最小权限：每 agent 独立 secrets、独立 workspace 挂载、最小工具集
- 供应链风险：第三方 skills 必须审计；默认 allowlist
- 控制面板/鉴权：任何“允许不安全鉴权”的模板默认值都必须被显式审查并在生产关闭

---

## 10. 分阶段 SOP（建议）

Phase 1（先跑通）：email + writing + personal
- 目标：任务闭环、artifact 规范、审计链路、成本守门

Phase 2：nox + metrics + growth
- 目标：指标/实验/路线图的跨日积累与可回放

Phase 3：trades + health
- 目标：高风险域严格 Review、强引用、强审计

---

## 11. Done Definition（可验证清单）

- 并行性：8 容器同时在线，互相不可读写对方 workspace
- 成本：24h 内 heartbeat 不触发推理；只有有任务才进入 LLM
- 一致性：同一任务不会被两 agent 重复 claim（锁 + 幂等）
- 可追溯：每任务可回放“指派 → 执行 → artifacts → review”
- 降级：WS 断线时系统仍可完成任务（仅缺实时感）
