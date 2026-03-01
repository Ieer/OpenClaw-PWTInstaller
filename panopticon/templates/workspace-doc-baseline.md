# Workspace 文档基线模板（8-Agent 通用）

用途：为任意新建或重构的 workspace 提供一套可直接落地的文档与目录标准，保证一致性、可审计、低成本心跳与可恢复执行。

适用目录：`panopticon/workspaces/<agent>/`

---

## 1) 必备文件（七件套）

- `AGENTS.md`：会话启动规则 + memory/skill/model/heartbeat 的统一策略
- `SOUL.md`：角色边界、数据边界、Review Gate、审计要求
- `USER.md`：用户偏好与协作风格速查
- `IDENTITY.md`：人设稳定锚点（Name/Creature/Vibe/Emoji/Avatar）
- `HEARTBEAT.md`：I/O-only 轮询清单（每次/每日/每周）
- `TOOLS.md`：本地环境特有工具笔记
- `MEMORY.md`：长期记忆索引（只存高价值摘要 + 引用）

---

## 2) 目录基线

```text
<workspace>/
  inbox/
  outbox/
  artifacts/
  state/
  sources/
  memory/
    projects.md
    infra.md
    lessons.md
    YYYY-MM-DD.md
    heartbeat-state.json
  skills/
    README.md
```

说明：

- `inbox/outbox/artifacts/state/sources` 是运行契约目录，不可省略。
- `memory/` 为结构化记忆层，避免单文件记忆膨胀。
- `skills/` 用于放置 workspace 级 `*/SKILL.md` 规范与实现。

---

## 3) AGENTS.md 必含策略段

### A. 会话预读顺序

1. 读 `SOUL.md`
2. 读 `USER.md`
3. 读 `memory/YYYY-MM-DD.md`（今天 + 昨天）
4. 主会话再读 `MEMORY.md`

### B. 记忆分层规则

- `MEMORY.md`：长期索引，不写流水
- `memory/projects.md`：项目状态
- `memory/infra.md`：环境与集成
- `memory/lessons.md`：经验与复盘
- `memory/YYYY-MM-DD.md`：当日日志

### C. `memorySearch` 约定

- 先检索再写入
- 有语义检索能力则优先语义召回
- 无语义检索能力时降级为 `memory/` 关键词检索
- 关键结论必须指向文件路径（memory/artifacts/sources）

### D. Skill 扩展约定

每个 skill 文档必须明确：

- 触发条件（Trigger）
- 执行步骤（Steps）
- 输出位置（Output）
- Review Gate（有外部副作用时必审）

### E. 模型分级路由（文档级）

- `small`：分类、抽取、格式化、短改写
- `medium`：分析、规划、跨源综合
- `large`：长文生成、复杂推理、高风险草案

原则：默认最小可用模型，因上下文复杂度或质量门槛再升级。

### F. 心跳原则（强约束）

- 心跳仅做 I/O 检查与状态刷新
- 禁止重推理、重生成、外部副作用
- 无事返回 `HEARTBEAT_OK`

---

## 4) HEARTBEAT.md 标准结构

建议固定四段：

1. `Rule Zero`（I/O-only + 禁止事项 + HEARTBEAT_OK）
2. `Every Heartbeat`（队列/状态/heartbeat-state 刷新）
3. `Daily (once)`（轻量清单，不执行外部动作）
4. `Weekly (once)`（把复用经验沉淀到 `memory/lessons.md` 与 `MEMORY.md`）

---

## 5) IDENTITY.md 规范

字段固定：

- `Name`
- `Creature`
- `Vibe`
- `Emoji`
- `Avatar`（workspace 相对路径或 URL）

要求：

- 不使用占位模板文本
- 人设应与 `SOUL.md` 角色一致，避免跨会话语气漂移

---

## 6) MEMORY.md 与 memory/* 写作规范

### MEMORY.md

- 只记录长期稳定信息 + 跳转索引
- 不直接堆叠原始日志

### projects.md

- `Active / Blocked / Next Review` 三段

### infra.md

- 集成说明 + guardrails（禁止明文密钥）

### lessons.md

- 只保留可复用经验，避免口水化记录

### YYYY-MM-DD.md

- 当天会话事实日志，供短期上下文读取

### heartbeat-state.json

- 必须保持“单一合法 JSON 对象”
- 推荐结构：

```json
{
  "lastChecks": {
    "queue": null,
    "state": null,
    "daily": null,
    "weekly": null
  },
  "runtime": {}
}
```

---

## 7) skills/README.md 最小模板

```markdown
# skills/README.md

本目录放置 workspace 级技能文档（`*/SKILL.md`）。

## Skill 规范
- Trigger
- Steps
- Output
- Review Gate
```

---

## 8) 验收清单（DoD）

- [ ] 七件套文件齐全且无占位文本
- [ ] `memory/` 分层文件齐全
- [ ] `HEARTBEAT.md` 明确 I/O-only 与 `HEARTBEAT_OK`
- [ ] `AGENTS.md` 含 memorySearch/skill/model-tier 策略
- [ ] `IDENTITY.md` 已实体化
- [ ] `heartbeat-state.json` 为单一合法 JSON
- [ ] `test_workspace_contract.py` 全量通过

---

## 9) 推荐落地步骤

1. 复制本模板对照新建 workspace 文档
  - 也可直接使用骨架包与脚本：
  - `panopticon/templates/workspace-skeleton/`
  - `python panopticon/tools/scaffold_workspace_docs.py --agent <slug>`
2. 先填 `SOUL/USER/IDENTITY`，再写 `HEARTBEAT`
3. 初始化 `MEMORY.md + memory/*`
4. 增加 `skills/README.md`
5. 运行：

```bash
python panopticon/tools/test_workspace_contract.py \
  --output panopticon/reports/workspace_contract_report_<tag>.json
```
