# lessons.md (trades)

## Reusable Lessons

- 每个结论必须附来源与假设
- 默认暴露不确定性与反例路径

## System/Workflow Lessons (from repeated patterns)

- **[DATA_MISSING]** 在没有配置数据源（价格feeds、新闻源、告警阈值）的情况下，所有论点都应标记 DATA_MISSING 不确定性标签
- **[NO_WATCHLIST]** 在没有配置监控标的的情况下，晨报和风险提示应明确标注 NO_WATCHLIST 状态
- 每次心跳检查都应确认 state/ 目录是否为空（无未解决的风险标志）
- 所有策略决策必须标记为 Review-required（符合 SOUL.md PWT 工作契约）

## Risk Boundary Lessons

- 不得在没有用户明确授权的情况下触发任何交易相关动作
- 任何可能影响真实资金/账户安全的动作都必须进入 Review gate