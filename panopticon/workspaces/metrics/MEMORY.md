# MEMORY.md - Long-Term Index (metrics)

仅记录高价值长期信息，并链接到详细文件；不堆叠日常流水。

## Stable Context

- 角色：metrics（指标/归因/异常检测）
- 高风险动作：对外发布与决策建议一律先 Review

## Index

- 项目状态：`memory/projects.md`
- 环境配置：`memory/infra.md`
- 经验教训：`memory/lessons.md`
- 每日日志：`memory/YYYY-MM-DD.md`

## Update Rule

- 先检索（`memorySearch` 或 `memory/` 关键词扫描）再写入
- 每次只沉淀可复用结论，不复制原文

## 长期必备技能

- **inner-map-skill-router**：认知基础设施系统，含对话管理/沟通教练/卓越校准/自我管理四个子技能 + knowledge 知识库。2026-04-25 安装完成。路径：`sources/inner-map-skill-router/`

## Inner-Map 集成约束

- 默认启用范围：main session 完成 SOUL/USER/memory 启动后，遇到混合意图、问题收敛、结论表达、长期校准、知识沉淀任务时，先用 inner-map 做首轮分流。
- 优先级：`SOUL.md` > `AGENTS.md` > inner-map skill 文档。SOUL 负责身份、边界、风格；inner-map 只负责分流与回答骨架。
- 任务系统 SSOT：`artifacts/`、`sources/`、`state/`、`memory/` 仍是 metrics 的默认任务证据系统。
- knowledge 提升条件：只有当内容明确需要长期指标知识沉淀、复用或结构优化时，才提升到 `sources/inner-map-skill-router/knowledge/`，不默认双写。
- 排除场景：清晰拉数、制图和格式化展示、窄执行型任务、heartbeat I/O 不强制走 inner-map。
- 正式建议边界：异常升级、归因判断、报告解释、对外数据结论这类 formal recommendation 仍优先走 `skills/knowledge-eval/`。
- 路由快规则：混乱、表达、复盘、沉淀先走 inner-map；异常判断、归因判断和可发布结论先走 knowledge-eval。