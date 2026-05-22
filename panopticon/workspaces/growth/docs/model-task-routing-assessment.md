# 基于任务自动选择模型 —— 实现可行性评估

## 需求拆解

> "基于任务自动选择最佳模型，兼顾预算，降低 token 消费"

三层含义：

1. **任务感知**：不依赖手动 `/model` 切换，自动判断任务复杂度/类型
2. **预算约束**：模型选择有成本上限，小任务用小模型，大任务用大模型
3. **降低消耗**：不浪费 token，不以「一刀切用最强模型」的方式来工作

---

## 一、现状能力盘点

### 已有基础设施

| 能力 | 状态 | 说明 |
|------|------|------|
| Fallback 链 | ✅ 完备 | `primary → fallbacks[]` 已配置，auth profile rotation + cooldown 全链路 |
| 多模型 allowlist | ✅ 完备 | `agents.defaults.models` 控制可见模型集 |
| `/model` 手动切换 | ✅ 完备 | 用户/系统可手动指定当前会话模型 |
| Session 级 model override | ✅ 完备 | auto/user 两档，persisted + rollback 安全 |
| Agent 级 model 绑定 | ✅ 完备 | `agents.list[].model` + 独立 fallbacks |
| 模型成本数据 | 🔶 部分 | `models.providers[].models[].cost` 已定义 input/output 单价 |
| Task complexity routing | ❌ 空缺 | 无原生机制区分"分类任务用 glm-4.7，规划任务用深新 v4" |
| Budget cap | ❌ 空缺 | 无会话/天/周 token 预算或成本限额 |

### 当前模型池

| 模型 | input 单价 (¥/M) | output 单价 (¥/M) | 适用场景 |
|------|------------------|-------------------|---------|
| `default/glm-4.7` | 2 | 8 | 分类、提取、格式化、简短改写 |
| `default/glm-5-turbo` | 5 | 22 | 分析、规划、跨来源综合（当前 primary） |
| `deepseek/deepseek-v4-flash` | 不确定 | 不确定 | 快速 fallback |
| `default/glm-4v` | 0 | 0 | 图片分析（imageOnly） |

---

## 二、核心思路与可选路径

### 路径 A：纯 AGENTS.md 策略层路由（零基础设施改动）

**原理**：在 `AGENTS.md` 声明模型分级路由策略，由 agent 在每次 reply 时根据任务复杂度自行选择：

```markdown
## Model Tier Routing (Policy-Only)

Use this document-level routing to control cost/quality:

- `small`: classification, extraction, formatting, short rewrites
- `medium`: analysis, planning, cross-source synthesis
- `large`: long-form generation, complex reasoning, high-stakes review drafts

Default to the smallest tier that can safely complete the task.
Escalate only when blocked by context depth or quality requirements.
```

**优点**：零配置、零代码、立即生效
**缺点**：靠 prompt，不是强约束，agent 可能不遵守；无自动化、无审计

**评估**：✅ **已部分实现（AGENTS.md 已有此策略）**，但无自动执行机制。

---

### 路径 B：基于 context 预算自动选择合适的 fallback 后段（OpenClaw 原生能力）

**原理**：利用已有的 `fallbacks[]` 机制，将低成本模型放在 chain 后面。

OpenClaw 的 fallback 实际行为：
- 正常运行时只用 `primary`
- primary 失败/过载/限速时走 fallback chain
- fallback 通过 `modelOverrideSource: "auto"` 持续生效直到 `/new` 或 `/reset`

**变体**：配置多组 fallback，根据不同入口（cron / agent / session）选择：
```json5
{
  agents: {
    list: [
      {
        id: "growth-main",
        model: {
          primary: "deepseek/deepseek-v4-flash",
          fallbacks: ["default/glm-4.7"]
        }
      },
      {
        id: "growth-small",
        model: {
          primary: "default/glm-4.7",
          fallbacks: []
        }
      }
    ]
  }
}
```

**优点**：全 Native 支持、有 cooldown/disable/rotation 保护
**缺点**：fallback 是"失败降级"而非"主动选择"，不能根据任务类型主动切换

**评估**：✅ 防崩场景好用，但不符合"任务感知主动选择"的需求。

---

### 路径 C：新建 Task Complexity Classifier 中间层

**原理**：在 agent 与模型之间加一个**轻量分类器**：在发起主要推理之前，先用极低成本模型判断当前输入的任务复杂度/类型，然后据此选择主模型。

```
用户输入 → 小模型分类器（glm-4.7 级别）
            ├── SMALL（提取/格式化）→ 直接用 glm-4.7
            ├── MEDIUM（分析/规划）→ 用 deepseek-v4-flash
            ├── LARGE（复杂推理/高风险评审）→ 用 glm-5-turbo
            └── IMAGE（图片任务）→ 用 glm-4v
```

**实现方式**：

#### 方案 C1：SKILL 层实现（推荐试点）

在 `sources/` 下新建 `model-router` skill，通过 skill trigger condition 在每轮对话前分流：

1. skill 读取输入，调用 `sessions_spawn` 或小模型做轻量分类
2. 分类结果写入 `state/model-router-state.json`
3. 后续主流程根据分类选择对应模型（通过 `session_status(model=...)` 或 fallback chain）

**关键问题**：
- 切换模型需要 `/model` 或 `sessions.patch`，这些是 user override，有严格约束
- 如果 session 已 fallback 到某个模型，再切换会触发重置
- 模型切换的上下文连续性：同一会话内切换模型会丢失对话历史（不同模型上下文引擎不同）

#### 方案 C2：Multi-Agent + 专用 routing agent（更可靠）

```
growth-agent（主 agent，处理所有用户对话）
  │
  ├── 配置为 primary model: deepseek/deepseek-v4-flash（中等成本，覆盖大部分）
  │
  ├── 发往 sub-agent（heavy）→ 使用 large model for 复杂推理
  │     使用 sessions_spawn + agentId = "growth-heavy"
  │     growth-heavy 的模型绑定为 glm-5-turbo
  │
  ├── 发往 sub-agent（light）→ 使用 small model for 提取/格式化
  │     使用 sessions_spawn + agentId = "growth-light"
  │     growth-light 的模型绑定为 glm-4.7
  │
  └── 决定权在 growth-agent 自身（用 medium model 做 routing 决策）
```

**优点**：
- 自然解决上下文独立问题（sub-agent 有独立会话）
- 只需要配置 `agents.list` + 主 agent 做 routing，无额外代码
- 主 agent 做 routing 的成本就是它自己的 primary model 的成本（已是最小化方案）

**评估**：🟢 **最可行、最自然、最有价值的路径**。

---

### 路径 D：外部 Proxy / 模型路由器（不推荐）

原理：在 OpenClaw 与模型 API 之间放一层 router（如 OpenRouter 的 model routing、自建 model gateway）。

**评估**：🔴 复杂度过高，运维负担大，与 OpenClaw 架构耦合低，收益有限。

---

## 三、推荐实现方案

### 短期（立即可用，零成本）

完善 `AGENTS.md` 的模型分级策略 + 主 agent 在每轮 reply 中主动判断任务类型并决策。

关键补充：

```markdown
## 任务分类规则（执行策略）

在每次回复前判断输入类型：

1. 如果是「分类/提取/格式化/简短改写」→ 使用 primary 模型即可（当前 primary 已足够小）
2. 如果是「分析/规划/跨来源综合」→ 使用 primary
3. 如果是「复杂推理/高风险评审/长文生成」→ spawn sub-agent with large model
4. 如果是「图片分析」→ 使用 imageModel
5. 如果是「普通聊天/日常回应」→ 使用 primary
```

**实际效果**：在当前的模型配置下（primary 已是中等成本的 glm-5-turbo），大部分场景用 primary 即可；
只有在碰到 complex reasoning 任务时额外 spawn sub-agent。已经做到了预算与质量的基本平衡。

### 中期（推荐试点）

**Multi-Agent 层级路由**（路径 C2）：

```
agents.list 配置：
├── growth (primary: deepseek-v4-flash, fallbacks: glm-4.7)
│   ├── 默认会话模型：deepseek-v4-flash（响应快，成本低）
│   ├── 自身 routing：用 deepseek-v4-flash 判断任务类型
│   ├── 复杂任务 → spawn growth-heavy (primary: glm-5-turbo)
│   └── 简单子任务 → spawn growth-light (primary: glm-4.7)
```

### 长期（最有价值）

**在 OpenClaw 内核中实现 task-aware model routing**：

- 加入 task complexity classifier 作为 channel pipeline 的一步
- 支持 `model.matchers` 配置：正则/输入长度/意图 → 自动选择模型级别
- 加入 `agents.defaults.model.tiers`：small / medium / large 三档，带成本上限
- 加入 `budget` 配置：session/token/cost cap，超过后自动降级模型

---

## 四、可行性总结

| 维度 | 评估 |
|------|------|
| 技术可行性 | ✅ **高**。OpenClaw 已有完善的 model/fallback/profile/agent 路由体系 |
| 架构兼容性 | ✅ **高**。Multi-agent 路由是设计内能力，无需 hack |
| 实现成本 | **短期 0 成本**（策略调整），中期 1-2 天（agent 配置），长期需 feature request |
| 预算效果 | 在 current primary 已中等成本的情况下，**主要节省来自 routing 决策层用更低成本模型** |
| 风险 | 低。sub-agent 独立运行，主会话不受影响 |
| 建议优先级 | 🥇 **短期先用路由策略**，🥈 **中期配 Multi-Agent**，🥉 **长期推 feature request** |

### 立即可以做的

当前 workspace 的 `AGENTS.md` **已经写了模型分级策略**（`small/medium/large`），**只需要在 reply 逻辑中增加 task-type gate**：

- 使用 `AGENTS.md` 已声明的 tier routing 作为 policy
- 在每轮 reply 中加一个预检步骤：判断任务类型 → 决定是否 spawn sub-agent
- 这不需要改任何配置，只是 agent 自身的行为约定

**结论**：思路 **完全可行**。建议 **先走策略层路由**（已在 AGENTS.md 中），**观察 token 消耗趋势后决定是否需要 Multi-Agent 配置**。
