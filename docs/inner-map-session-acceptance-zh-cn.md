# Inner-Map 使用说明

这篇文档面向第一次接触 Inner-Map 的用户。目标不是教你跑验收，而是先让你知道：Inner-Map 是什么、解决什么问题、什么时候该用、什么时候不该用。

如果你要看正式验收清单，直接看 [../panopticon/reports/inner-map-session-acceptance-2026-04-25.md](../panopticon/reports/inner-map-session-acceptance-2026-04-25.md)。

## 一句话理解

Inner-Map 不是另一个角色 agent，也不是一个单独的知识库产品。它更像一个“首轮路由器 + 回答结构约束”，用来处理这类问题：

- 用户输入很混乱，暂时还不能直接给判断。
- 问题里同时混着情绪、事实、表达、决策和长期沉淀需求。
- 需要先把问题收敛，再决定进入沟通、校准、评估还是知识整理。

简单说：它先帮你把问题看清，再决定往哪条路走。

## Inner-Map 主要负责什么

当前仓库里的 Inner-Map 总入口在 [panopticon/workspaces/nox/sources/inner-map-skill-router/SKILL.md](../panopticon/workspaces/nox/sources/inner-map-skill-router/SKILL.md)。它不直接承载所有细节，而是负责把问题分流到 4 个子方向：

| 子方向 | 适合什么问题 | 典型结果 |
| --- | --- | --- |
| 对话管理 | 用户很乱、不知道先做什么、事实和情绪混在一起 | 先收敛问题，再给最小下一步 |
| 沟通教练 | 需要回复、汇报、解释、说服、拒绝 | 先明确对象、结构、语气和风险，再生成说法 |
| 卓越校准 | 想做 7/30/90 天校准、复盘、长期成长设计 | 形成阶段目标、差距和行动路径 |
| 自我管理 | 想把对话里的高价值信息提炼并沉淀 | 先提炼，再判断是否值得归档 |

## 什么时候应该先走 Inner-Map

如果用户的问题更像下面这些信号，通常应该先走 Inner-Map：

- “我现在很乱，不知道先做哪件事。”
- “我知道有问题，但还不会把它说清楚。”
- “帮我先拆开事实、情绪和判断。”
- “我想复盘一下，把值得保留的东西整理出来。”
- “这段对话里哪些内容值得长期沉淀？”

此时最重要的不是马上下结论，而是先把问题结构化。

## 什么时候不要停留在 Inner-Map

如果问题已经进入正式判断阶段，就不该一直停在 Inner-Map。

这类场景通常应切到 `knowledge-eval`：

- release 要不要继续推
- roadmap 哪个方案优先
- 项目继续 / 暂停 / 停止
- 风险、依赖、回滚代价、影响评估
- 产品或运营上的正式 recommendation

一句话判断：

- “我很乱、我不会说、我想先梳理” -> 先走 Inner-Map。
- “是否继续、哪个优先、风险多大、要不要发布” -> 直接走 knowledge-eval。

## Inner-Map 和 knowledge-eval 的关系

两者不是替代关系，而是前后协作关系。

| 场景 | 先做什么 | 最终输出 |
| --- | --- | --- |
| inner-map | 先收敛、分层、澄清 | 清晰问题定义和可执行下一步 |
| knowledge-eval | 直接正式判断 | options、risks、dependencies、decision points |
| hybrid | 先 Inner-Map，再 knowledge-eval | 先把问题讲清，再给正式 recommendation |

最常见的错误是顺序反了：问题还没收敛，就直接给 formal recommendation。Inner-Map 的意义就是避免这种过早判断。

## 用户应该期待什么样的回答

在 Inner-Map 路由下，回答通常有这些特征：

- 先拆开事实、解释、情绪和判断。
- 先帮你明确当前真正的问题是什么。
- 风格短句、直接、可执行。
- 不越过 Review Gate 直接做外部副作用动作。
- 不默认把内容双写到知识库；只有明确值得长期沉淀时，才提升归档。

所以，如果你看到的第一反应是“先把问题讲清”，而不是“直接告诉你做 A 还是做 B”，这通常说明 Inner-Map 在按预期工作。

## 在当前仓库里，Inner-Map 是怎么接进去的

当前 Panopticon 里，Inner-Map 已接入 8 个 agent：

- `nox`
- `email`
- `growth`
- `health`
- `metrics`
- `personal`
- `trades`
- `writing`

每个已接入的 workspace，通常有 4 类落点：

1. `sources/inner-map-skill-router/SKILL.md`：技能总入口。
2. `AGENTS.md`：声明何时优先走 Inner-Map、何时切到 knowledge-eval。
3. `USER.md`：声明输出、落盘和协作边界。
4. `MEMORY.md`：记录长期集成约束。

这意味着 Inner-Map 不是“只在 nox 里试验”的局部能力，而是已经成为 8-Agent 体系中的通用首轮路由能力。

## 为什么 nox 是基线

当前验收设计里，`nox` 被当作基线 agent 使用。原因不是它特殊，而是它最早完成了双路由设计，可以作为其它角色的对照面。

判读规则很简单：

- `nox` 和多个角色一起偏离：优先怀疑共用路由规则。
- 只有某个角色偏离：优先怀疑该角色的特化文档写法。

如果你要看这套基线如何被正式验证，直接看验收报告，不需要在这篇说明里找 prompt 明细。

## 想继续往下看什么

按你的目的继续读：

- 想看正式验收清单和 prompt：看 [../panopticon/reports/inner-map-session-acceptance-2026-04-25.md](../panopticon/reports/inner-map-session-acceptance-2026-04-25.md)
- 想看仓库中的主路线运行方式：看 [../panopticon/README.md](../panopticon/README.md)
- 想看知识系统与 formal evaluation 怎么协作：看 [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) 和 [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md)

## 当前状态

- Inner-Map 已接入 8 个 agent。
- `nox` 作为基线已纳入正式验收范围。
- 静态前置已通过；运行时会话验收仍应按报告逐个执行。