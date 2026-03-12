# MEMORY.md - Long-Term Index (nox)

仅记录高价值长期信息，并链接到详细文件；不堆叠日常流水。

## Stable Context

- 角色：nox（产品运营与 roadmap 建议）
- 高风险动作：涉及外部承诺/上线影响动作一律 Review
- Heartbeat：I/O-only 模式，每 30 分钟检查一次
- 每周回顾：每周初更新 lessons.md 和 MEMORY.md（上次：2026-03-11）

## Index

- 项目状态：`memory/projects.md`
- 环境配置：`memory/infra.md`
- 经验教训：`memory/lessons.md`
- 每日日志：`memory/YYYY-MM-DD.md`
- 周回顾：`memory/YYYY-MM-DD-weekly.md`

## 历史任务

- **lyrics-collaboration-2026-02-25**（已完成，等待决策）：3 套歌词方案 + 3 条路线建议 → `artifacts/lyrics-collaboration-2026-02-25/`
- **year-end-party-2026**（已完成）：尾牙活动费用追踪与结算，17人参与，最终结算已确认 → `memory/2026-03-07.md`

## Update Rule

- 先检索（`memorySearch` 或 `memory/` 关键词扫描）再写入
- 每次只沉淀可复用结论，不复制原文

## 运营模式

- **Daily Pulse**: 每天北京时间 0:00（UTC 16:00）自动运行，输出风险/阻塞/依赖/Review 需求
- **Weekly Review**: 每周一运行，总结 lessons 并更新 MEMORY.md
- **项目清理**: 超过 10 天等待用户决策的任务标记归档建议