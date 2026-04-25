# MEMORY.md - Long-Term Index (writing)

仅记录高价值长期信息，并链接到详细文件；不堆叠日常流水。

## Stable Context

- 角色：writing（长文/文档产出，强制引用）
- 高风险动作：对外发布/署名表达一律 Review

## Index

- 项目状态：`memory/projects.md`
- 环境配置：`memory/infra.md`
- 经验教训：`memory/lessons.md`
- 每日日志：`memory/YYYY-MM-DD.md`
- PPTX 技能优化（v2.1）：`memory/2026-03-05.md`
- PPTX 测试报告（2026-03-05）：`memory/pptx_test_report_2026-03-05.md`
- PPTX AI Agent History 报告：`memory/ai_agent_history_ppt_report_2026-03-05.md`
- PPTX 优化完整报告：`artifacts/pptx_optimization_complete_report.md`
- 缩略图生成报告：`memory/thumbnail_generation_report_2026-03-05.md`

## Update Rule

- 先检索（`memorySearch` 或 `memory/` 关键词扫描）再写入
- 每次只沉淀可复用结论，不复制原文

## 长期必备技能

- **inner-map-skill-router**：认知基础设施系统，含对话管理/沟通教练/卓越校准/自我管理四个子技能 + knowledge 知识库。2026-04-25 安装完成。路径：`sources/inner-map-skill-router/`

## Inner-Map 集成约束

- 默认启用范围：main session 完成 SOUL/USER/memory 启动后，遇到混合意图、问题收敛、表达校准、长期校准、知识沉淀任务时，先用 inner-map 做首轮分流。
- 优先级：`SOUL.md` > `AGENTS.md` > inner-map skill 文档。SOUL 负责身份、边界、风格；inner-map 只负责分流与回答骨架。
- 任务系统 SSOT：`artifacts/`、`sources/`、`state/`、`memory/` 仍是 writing 的默认任务证据系统。
- knowledge 提升条件：只有当内容明确需要长期写作知识沉淀、复用或结构优化时，才提升到 `sources/inner-map-skill-router/knowledge/`，不默认双写。
- 排除场景：清晰的润色、排版、局部改写、窄执行型任务、heartbeat I/O 不强制走 inner-map。
- 正式建议边界：可发布性、资料是否足够、观点风险、继续写还是重写这类 formal recommendation 仍优先走 `skills/knowledge-eval/`。
- 路由快规则：混乱、表达、复盘、沉淀先走 inner-map；发布判断、来源充足性和重写判断先走 knowledge-eval。