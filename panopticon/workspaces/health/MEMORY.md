# MEMORY.md - Long-Term Index (health)

仅记录高价值长期信息，并链接到详细文件；不堆叠日常流水。

## Stable Context

- 角色：health（睡眠/训练/恢复建议）
- 高风险动作：任何医疗/不可逆建议一律 Review

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

- 默认启用范围：main session 完成 SOUL/USER/memory 启动后，遇到混合意图、问题收敛、边界沟通、长期校准、知识沉淀任务时，先用 inner-map 做首轮分流。
- 优先级：`SOUL.md` > `AGENTS.md` > inner-map skill 文档。SOUL 负责身份、边界、风格；inner-map 只负责分流与回答骨架。
- 任务系统 SSOT：`artifacts/`、`sources/`、`state/`、`memory/` 仍是 health 的默认任务证据系统。
- knowledge 提升条件：只有当内容明确需要长期健康知识沉淀、复用或结构优化时，才提升到 `sources/inner-map-skill-router/knowledge/`，不默认双写。
- 排除场景：纯事实查询、窄执行型任务、紧急风险信号、heartbeat I/O 不强制走 inner-map。
- 正式建议边界：continue/stop、强度调整、风险/禁忌判断这类 formal recommendation 仍优先走 `skills/knowledge-eval/`。
- 路由快规则：混乱、表达、复盘、沉淀先走 inner-map；计划取舍和风险判断先走 knowledge-eval。