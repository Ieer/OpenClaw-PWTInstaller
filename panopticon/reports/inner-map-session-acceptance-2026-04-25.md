# Inner-Map Batch Session Acceptance Checklist

日期：2026-04-25

范围：本清单覆盖 8 个已接入 inner-map 的 agent。

- nox
- email
- growth
- health
- metrics
- personal
- trades
- writing

说明：本轮先完成静态前置验收，并输出可直接执行的会话验收清单。`nox` 作为基线 agent，现纳入本批次 8 个 agent 的清单范围，并建议作为第一站先跑。

## 静态前置验收结论

已确认以下前置全部满足：

1. 8 个 workspace 均存在 `sources/inner-map-skill-router/SKILL.md`。
2. 8 个 `AGENTS.md` 均包含 `Inner-Map Default Router`、`Knowledge Evaluation Default`、`Quick rule`。
3. 8 个 `USER.md` 均包含路由快规则。
4. 8 个 `MEMORY.md` 均包含长期必备技能与 `Inner-Map 集成约束`。

静态状态：8 / 8 Ready。

## 通用会话通过标准

### A. inner-map 场景通过标准

- 首轮响应先做收敛、分层、表达校准、复盘或知识提炼，而不是直接给 formal recommendation。
- 响应风格保持短句、直接、可执行。
- 不越过 workspace 的 Review Gate 和落盘边界。
- 如需长期沉淀，应表达为“可提升到 inner-map knowledge”，而不是默认双写。

### B. knowledge-eval 场景通过标准

- 首轮响应直接进入正式判断，不继续停留在收敛模式。
- 输出包含该 agent 文档约定的判断维度，如风险、约束、依赖、确认项、停损条件、来源边界等。
- 在证据不足时，明确保留不确定性，不做过度断言。

### C. hybrid 场景通过标准

- 第一阶段先用 inner-map 收敛问题、澄清目标、拆分事实与判断。
- 第二阶段切到 knowledge-eval，给 formal recommendation。
- 顺序必须是“先收敛，后评估”，不能反过来。

## nox 基线使用方式

- `nox` 既是验收对象，也是本轮路由基线；建议先执行 `nox`，再跑其它 7 个角色。
- 如果 `nox` 和其它 agent 出现相同偏差，优先判断为共用路由规则或 skill 合同问题。
- 如果只有单个角色 agent 偏离，而 `nox` 正常，优先修该角色的 `AGENTS.md`、`USER.md`、`MEMORY.md`。
- `nox` 的 knowledge-eval 结果应特别体现 options、risks、dependencies、required user decisions。

## 执行顺序建议

按下面顺序逐个开 main session 执行：

1. nox
2. email
3. growth
4. health
5. metrics
6. personal
7. trades
8. writing

每个 agent 连续跑 3 条 prompt：

- 1 条 inner-map
- 1 条 knowledge-eval
- 1 条 hybrid

## Agent Checklist

### nox

inner-map prompt：

> 现在 backlog、release、协作方反馈和未决事项全混在一起，我不知道先拆哪块，也不知道怎么跟团队同步更稳。

期望：先走 inner-map；先收敛问题，再拆开事实、情绪、判断和同步对象。

knowledge-eval prompt：

> 这个 release 现在要不要继续推？如果继续，最大的风险、依赖和回滚代价分别是什么？

期望：直接走 knowledge-eval；输出继续/暂缓判断、风险、依赖、回滚代价和需要用户决定的点。

hybrid prompt：

> 我现在很乱，但最终要决定这个项目是继续推进、降级范围，还是先暂停。

期望：先收敛目标、约束和选项，再切到正式评估，不直接跳结论。

### email

inner-map prompt：

> 收件箱里有催办、投诉、内部同步和未决事项，我不知道先处理哪封，也不确定怎么回才不会说错话。

期望：先走 inner-map；先收敛问题，再拆分对象、优先级、承诺边界。

knowledge-eval prompt：

> 这封投诉邮件现在该不该回，还是先等更多信息？如果要回，风险最大的点是什么？

期望：直接走 knowledge-eval；评估时机、目标、误伤风险、是否需要升级或 Review。

hybrid prompt：

> 我现在情绪很乱，但最终要决定这封邮件是直接回、升级，还是先等。

期望：先收敛，再正式评估，不直接跳到结论。

### growth

inner-map prompt：

> 现在渠道、漏斗、文案、实验都混在一起，我不知道先看哪块，也不知道该怎么跟团队解释。

期望：先走 inner-map；先聚焦问题，再整理假设、约束和最小动作。

knowledge-eval prompt：

> 这个实验要不要继续跑到下周，还是现在就停？如果继续，最大的机会成本是什么？

期望：直接走 knowledge-eval；输出继续/停止判断、停止条件、指标和风险。

hybrid prompt：

> 我现在很乱，但最终要决定这个实验是继续、暂停还是终止。

期望：先收敛实验目标和冲突信号，再切到正式判断。

### health

inner-map prompt：

> 最近睡眠、训练、压力都乱了，我不知道先调哪一块，也不太会跟教练解释。

期望：先走 inner-map；先区分事实、主观感受、风险，再给最小下一步。

knowledge-eval prompt：

> 这个训练计划下周还要不要继续，还是该减量？如果减量，依据应该是什么？

期望：直接走 knowledge-eval；输出继续/减量判断、风险、确认项和替代方案。

hybrid prompt：

> 我最近状态很乱，但最终要判断这个训练计划是继续还是减量。

期望：先收敛症状和限制条件，再给 formal recommendation。

### metrics

inner-map prompt：

> 我手上有几组指标、几个假设和几条异常线索，但不知道先看哪个，也不知道怎么跟业务解释。

期望：先走 inner-map；先收敛分析边界，再整理证据与表达风险。

knowledge-eval prompt：

> 这个异常指标要不要升级为事故？如果现在写进周报，最危险的误判是什么？

期望：直接走 knowledge-eval；输出异常判断、证据强度、缺口和下一步验证。

hybrid prompt：

> 我现在对几组指标很乱，但最终要判断这是不是事故、能不能写进周报。

期望：先收敛问题，再切到正式评估。

### personal

inner-map prompt：

> 订阅、报销、行程和待办全卡在一起，我不知道先处理哪个，也不知道怎么跟对方沟通更稳。

期望：先走 inner-map；先收敛个人任务冲突，再给最小下一步。

knowledge-eval prompt：

> 这个订阅要不要现在取消，还是再观察一个月？哪个方案更稳？

期望：直接走 knowledge-eval；输出 keep/cancel 判断、成本、后果和 Review 点。

hybrid prompt：

> 我对改签这件事很乱，但最终要决定退还是改。

期望：先收敛约束、预算和时间窗口，再给 formal recommendation。

### trades

inner-map prompt：

> 盘面信息太多，我现在分不清哪些是噪音、哪些值得盯，也不知道怎么把想法表达得不过头。

期望：先走 inner-map；先收敛研究焦点，再整理事实、判断与表达边界。

knowledge-eval prompt：

> 这个 setup 现在还要继续盯，还是先放弃？如果继续，最关键的失效条件是什么？

期望：直接走 knowledge-eval；输出 thesis judgement、风险、反证和等待成本。

hybrid prompt：

> 我现在思路很乱，但最终要决定这个 setup 是继续盯还是放弃。

期望：先收敛，再正式判断，不直接隐含执行 readiness。

### writing

inner-map prompt：

> 主题、受众、观点和材料全混在一起，我不知道这篇文章该从哪下手，也不确定语气要多强。

期望：先走 inner-map；先收敛写作目标、受众和来源边界。

knowledge-eval prompt：

> 这篇稿子的资料够不够支撑发布？如果继续写，最危险的来源缺口是什么？

期望：直接走 knowledge-eval；输出 publishability、source sufficiency、缺口和限制。

hybrid prompt：

> 我现在思路很乱，但最终要判断这篇稿是继续写、重构，还是暂时停下。

期望：先收敛主题和证据边界，再给 continue/rewrite judgement。

## 会话记录模板

每个 agent 跑完 3 条 prompt 后，用以下格式记录：

- Agent：
- Inner-map：Pass / Fail / Partial
- Knowledge-eval：Pass / Fail / Partial
- Hybrid：Pass / Fail / Partial
- 观察：
- 偏差：
- 是否需要修文档：Yes / No

## 批量验收判定规则

- 8 个 agent 全部通过 3 类场景：批量验收通过。
- 任一 agent 的 hybrid 失败：优先修 AGENTS.md 的切换规则。
- 任一 agent 的 knowledge-eval 输出缺少本角色要求的判断维度：优先修 `Knowledge Evaluation Default` 段。
- 任一 agent 把 inner-map 场景直接答成 formal recommendation：优先修 `Inner-Map Default Router` 和 `Quick rule`。
- 如果 `nox` 与其它 agent 同时出现同类偏差：优先修共用规则，再回看角色特化文档。

## 当前结论

- 静态前置：通过（8 / 8 Ready，含 `nox` 基线）。
- 会话清单：已就绪，可直接执行。
- 运行时对话结果：待按本清单逐个 session 验收。