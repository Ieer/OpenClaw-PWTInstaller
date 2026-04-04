# 8-Agent 共用评估调用规范（简中）

本规范定义 `nox / metrics / email / growth / trades / health / writing / personal` 这 8 个 Agent 在 Panopticon + Mission Control 架构下，如何统一调用知识系统完成“资料评估”。目标不是让每个 Agent 各写一套检索逻辑，而是把正式评估统一收口到 Mission Control 的知识治理链路。

适用范围：

- 正式问答前的资料评估
- 任务执行前的依据校验
- 创作前的背景整理与证据提取
- 高风险任务的约束检查

不适用范围：

- 知识导入与切片
- validation 写入与治理后台操作
- 纯闲聊或纯格式整理

## 1. 设计原则

### 1.1 双层知识使用模式

8 个 Agent 的知识使用统一采用“双层模式”：

- **静态核心层**：通过 workspace 会话预读加载 `SOUL.md`、`USER.md`、`MEMORY.md` 与近期 memory 文件，承载角色边界、长期约束、固定 SOP。
- **动态评估层**：通过 Mission Control 的 `POST /v1/knowledge/resolve` 评估当前任务所需资料。

原因：

- 稳定规则需要“确定命中”，不应依赖检索碰运气。
- 动态资料需要过滤、验证、排序、审计，不应回退到 Agent 侧重复实现。

### 1.2 统一评估入口

正式评估统一使用：

- `POST /v1/knowledge/resolve`

不建议默认把 `POST /v1/knowledge/search` 作为正式评估主入口，因为 `search` 更适合探索式检索，不负责完整的 validation policy、ranking profile 与审计闭环。

### 1.3 Agent 只负责传入任务上下文

Agent 侧职责只包括：

- 识别当前任务是否需要评估
- 构造统一请求字段
- 消费 `resolve` 返回的 knowledge package
- 以统一模板输出“结论 + 依据 + 限制”

Agent 不负责：

- 自己做知识可信度判断
- 自己拼 lexical / semantic 候选
- 自己决定 approved / expired / confidence 等校验逻辑

这些职责统一由 Mission Control 后端承担。

## 2. 统一调用时机

### 2.1 必须调用的场景

以下场景默认必须先调一次 `resolve`：

1. 需要引用历史资料、外部文档、策略规则、知识单元时。
2. 需要输出“判断、建议、比较、评估、方案”时。
3. 任务会影响预算、发布、对外沟通、执行动作时。
4. 任务风险级别为 `normal / high / critical` 且需要可解释依据时。
5. 任务需要区分公共知识与 Agent 专属知识时。

### 2.2 可以不调用的场景

以下场景可以跳过 `resolve`：

1. 纯闲聊。
2. 纯格式化、排版、转写。
3. 当前会话上下文已足够完成的微任务。
4. 仅依赖 workspace 静态规则即可完成的固定动作。

### 2.3 推荐触发规则

建议统一实现以下触发规则：

- 任务出现“评估 / 判断 / 建议 / 是否继续 / 是否执行 / 风险 / 依据”等意图时，默认触发 `resolve`。
- 任务只是“找一下相关资料”时，可先走 `search`，若后续需要正式结论，再升级为 `resolve`。

## 3. 统一请求字段规范

`KnowledgeResolveIn` 的服务端字段定义以 `mission_control_api/app/schemas.py` 为准。

### 3.1 必填字段

- `task`
- `agent_slug`
- `risk_level`

### 3.2 常规可选字段

- `tags`
- `limit`
- `retrieval_mode`
- `ranking_profile`
- `source_type`

### 3.3 高级控制字段

- `semantic_query`
- `semantic_limit`
- `embedding_model`
- `embedding_dimensions`
- `min_semantic_similarity`
- `min_score`
- `require_approved_validation`
- `include_rejected`

## 4. 字段填写规则

### 4.1 task

`task` 必须是完整问题描述，不允许只写关键词。

建议写法：

- 说明当前要评估什么
- 说明判断目标是什么
- 说明希望优先考虑哪些约束

推荐示例：

- `评估本周增长实验是否应继续投放，优先关注转化率、样本量和历史同类实验结论。`
- `判断这封营销邮件是否适合在当前活动阶段发送，并给出风险与修改建议。`
- `评估当前交易策略是否适合执行，优先参考近期风险规则、仓位约束和验证通过的市场知识。`

### 4.2 agent_slug

`agent_slug` 必须来自 8-Agent 清单，不允许传 role 文本或 UI 名称。

固定取值：

- `nox`
- `metrics`
- `email`
- `growth`
- `trades`
- `health`
- `writing`
- `personal`

### 4.3 risk_level

允许值：

- `low`
- `normal`
- `high`
- `critical`

建议含义：

- `low`：灵感、草案、弱约束建议
- `normal`：一般业务判断
- `high`：涉及预算、发布、重要计划、执行建议
- `critical`：涉及不可逆动作、重大承诺、财务或健康高风险

默认 validation 规则以知识系统后端为准：

- `low`：默认不强制校验
- `normal`：默认要求 `approved`
- `high`：默认要求 `approved + 未过期 + confidence>=0.7 + 30天内验证`
- `critical`：默认要求 `approved + 未过期 + confidence>=0.85 + 14天内验证`

### 4.4 tags

`tags` 用于缩小候选集，建议控制在 0 到 5 个。

推荐风格：

- nox：`roadmap`, `product`, `priority`
- metrics：`metric`, `dashboard`, `analysis`
- email：`campaign`, `copy`, `deliverability`
- growth：`experiment`, `funnel`, `activation`
- trades：`risk`, `position`, `market`
- health：`sleep`, `training`, `recovery`
- writing：`style`, `outline`, `reference`
- personal：`budget`, `subscription`, `travel`

### 4.5 limit

建议默认：

- `5`

建议范围：

- 常规评估：`3-5`
- 复杂比较：`5-8`
- 不建议默认超过 `10`

### 4.6 retrieval_mode

建议规则：

- 默认 `hybrid`
- 规则文本、术语匹配优先：`lexical`
- 经验复用、语义近似优先：`semantic`

正式评估默认使用 `hybrid`。

### 4.7 ranking_profile

建议规则：

- 默认 `balanced`
- 高风险任务优先 `precision`

### 4.8 source_type

只有当明确知道需要限制知识来源时才填写，例如：

- 只看某类文档来源
- 只看特定治理链路下的知识源

## 5. 首版下沉实现

当前仓库已开始把这份规范下沉为共享 skill，请优先复用以下实现，而不是让每个 Agent 单独拼接 HTTP 请求：

- `panopticon/global-skills/knowledge-eval/SKILL.md`
- `panopticon/global-skills/knowledge-eval/scripts/knowledge_eval.py`
- `panopticon/global-skills/knowledge-eval/examples/*.json`

首版实现策略：

- **主落点**：skill 层共享请求封装
- **后续增强**：若需要减少显式调用，再补 wrapper 层，只做默认参数注入与触发门槛判断
- **不放在客户端的逻辑**：validation policy、ranking、agent_scope 过滤、audit

建议调用顺序：

1. Agent 先判断当前任务是否属于“正式评估”场景。
2. 通过 `knowledge-eval` 统一构造 `resolve` 请求。
3. 读取 `summary.status / top_items / constraints / recommended_action`。
4. 再按 Agent 自己的角色模板输出最终评估结论。

不明确时留空。

### 4.9 require_approved_validation

建议规则：

- `low` 与 `normal` 默认留空
- `high` 与 `critical` 默认留空，让后端按风险自动收紧
- 只有在调试或业务明确要求更宽松/更严格时才显式传值

### 4.10 include_rejected

建议默认：

- `false`

仅在调试、审计、复盘场景下设为 `true`。

## 5. 推荐请求模板

### 5.1 通用默认模板

```json
{
  "task": "请描述本次要评估的任务、目标和判断重点",
  "agent_slug": "nox",
  "risk_level": "normal",
  "tags": [],
  "limit": 5,
  "retrieval_mode": "hybrid",
  "ranking_profile": "balanced",
  "include_rejected": false
}
```

### 5.2 高风险模板

```json
{
  "task": "请描述本次高风险任务、决策背景、限制条件和评估目标",
  "agent_slug": "trades",
  "risk_level": "high",
  "tags": ["risk", "position"],
  "limit": 5,
  "retrieval_mode": "hybrid",
  "ranking_profile": "precision",
  "include_rejected": false
}
```

### 5.3 调试模板

```json
{
  "task": "评估当前邮件投放建议是否符合已验证规则",
  "agent_slug": "email",
  "risk_level": "normal",
  "tags": ["campaign", "copy"],
  "limit": 5,
  "retrieval_mode": "hybrid",
  "ranking_profile": "balanced",
  "include_rejected": true
}
```

## 6. 统一响应解释规范

返回结构以 `KnowledgeResolveOut` 为准。

核心字段：

- `task`
- `agent_slug`
- `risk_level`
- `total`
- `rejected_count`
- `items[]`
- `rejected[]`

每个 `items[]` 中重点关注：

- `unit`
- `validation_status`
- `validation_expires_at`
- `score`
- `semantic_similarity`
- `retrieval_channels`
- `score_breakdown`

解释顺序建议：

1. 是否有命中 `items`
2. 命中项是否已验证
3. 检索通道是 lexical / semantic / hybrid
4. 排序分值是否明显集中
5. 是否存在大量 rejected，以及拒绝原因是什么

## 7. 统一输出模板

8 个 Agent 消费 `resolve` 结果后，统一使用三段输出：

1. 评估结论
2. 命中知识
3. 可信度与限制

### 7.1 通用文本模板

```text
【评估结论】
本次任务：{task简述}
建议：{继续 / 暂缓 / 修改后继续 / 需要人工确认}
原因：{一句话总结}

【命中知识】
1. {unit.title}：{关键结论}
2. {unit.title}：{关键结论}
3. {unit.title}：{关键结论}

【可信度与限制】
- 风险级别：{risk_level}
- 验证状态：{approved / 未验证 / 已过期 / 混合}
- 检索通道：{lexical / semantic / hybrid}
- 约束：{资料不足 / 存在拒绝项 / 部分证据时效性有限}
```

### 7.2 结构化模板

```json
{
  "decision": {
    "summary": "",
    "recommended_action": "continue",
    "reason": ""
  },
  "evidence": [
    {
      "unit_key": "",
      "title": "",
      "validation_status": "approved",
      "retrieval_channels": ["hybrid"],
      "summary": ""
    }
  ],
  "trust_notes": {
    "risk_level": "normal",
    "constraints": [],
    "rejected_count": 0
  }
}
```

## 8. 无命中与弱命中的处理规范

### 8.1 无命中

当 `total = 0` 时：

- 不允许伪造依据
- 必须明确说明“当前知识库未提供足够支持”
- 高风险任务默认降级为人工确认

推荐模板：

```text
【评估结论】
当前未命中足够知识，暂不建议基于知识库直接下结论。

【原因】
- 未返回可用知识包
- 当前任务可能缺少对应知识源、标签或验证通过的资料

【建议动作】
1. 补充更具体的 task 描述后重试
2. 指定 tags 或 source_type 缩小范围
3. 若任务高风险，转人工确认
```

### 8.2 弱命中

当有命中但 `validation_status` 弱、证据分散或约束明显时：

- 只能输出倾向性判断
- 不允许把弱证据表述成确定结论

推荐表述：

- `基于当前已检索知识，倾向于……`
- `现有资料支持度有限，建议……`
- `当前命中资料可作参考，但不建议直接执行……`

## 9. 8 个 Agent 的默认风险建议

- `nox`：默认 `normal`，涉及路线图承诺升到 `high`
- `metrics`：默认 `normal`，涉及经营判断升到 `high`
- `email`：默认 `normal`，涉及真实发送升到 `high`
- `growth`：默认 `normal`，涉及真实用户实验升到 `high`
- `trades`：默认 `high`，涉及真实执行可升到 `critical`
- `health`：默认 `high`，涉及具体干预建议可升到 `critical`
- `writing`：默认 `low` 或 `normal`，涉及正式对外发布升到 `high`
- `personal`：默认 `normal`，涉及支付、取消、提交升到 `high`

## 10. 实现建议

若后续在 Agent wrapper 或 skills 层实现统一调用，建议固定一个共用函数：

输入：

- `task`
- `agent_slug`
- `risk_level`
- `tags`
- `context_overrides`

输出：

- `decision_summary`
- `evidence_items`
- `trust_notes`
- `raw_resolve_payload`

实现原则：

- 8 个 Agent 只差异化传参，不差异化造轮子
- 静态规则优先来自 workspace 预读
- 动态资料评估统一走 `resolve`
- `search` 仅作为探索补充，不作为正式评估主链路

## 11. 维护原则

这份规范应与以下文档保持一致：

- `README.md`：PWT 价值与主路线说明
- `panopticon/README.md`：8-Agent 架构与知识链路说明
- `docs/knowledge-system-playbook-zh-cn.md`：知识系统行为与治理口径
- `mission_control_api/app/schemas.py`：真实接口字段定义

如果服务端字段或行为发生变更，应优先更新本规范，再同步 README 与 playbook 中的引用口径。