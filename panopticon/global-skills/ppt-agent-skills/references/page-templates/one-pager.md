# 单页简报模板

> 面向 executive one-pager / 一页简报。用于把一个主题压缩成可决策的一页，而不是生成封面。

## 适用场景

- 用户明确要求“一页 PPT / 一页简报 / one-page briefing / executive one-pager”。
- 给老板、客户、投资人快速同步关键事实和建议。
- 项目周报、经营复盘、问题诊断、方案摘要、会议预读材料。

## 信息架构

单页简报必须同时具备 5 类信息：

1. **Executive takeaway**：一句话结论，回答“这页要我相信什么/决定什么”。
2. **Context**：为什么现在要看这件事，限制在 1 行或 1 个轻卡片。
3. **Evidence / KPI**：2-4 个关键数字、事实或对比。
4. **Implication**：这些事实意味着什么，通常由主洞察卡承载。
5. **Action / Risk**：建议动作、风险、下一步，不允许缺席。

## Planning 要求

- `page_type` 使用 `content`，不要使用 `cover`。
- `layout_hint` 优先使用 `one-pager-grid`。
- `visual_weight` 通常为 `8` 或 `9`。
- `negative_space_target` 可设为 `low`，但必须保留标题区和页脚安全区。
- `resources.principle_refs` 必须包含 `visual-hierarchy`、`composition`、`cognitive-load`。
- `resources.resource_rationale` 必须说明阅读顺序和信息压缩策略。
- `source_guidance.citation_expectation` 必须说明来源条或脚注策略。

## 卡片建议

推荐 4-6 张主卡：

| 角色 | 建议内容 | 推荐类型 |
|------|----------|----------|
| anchor | 主洞察、核心图表、关键判断 | `data_highlight` / `diagram` / `comparison` |
| support | KPI 1-3、状态、证据点 | `data` / `data_highlight` |
| context | 背景、范围、约束 | `text` / `list` |
| support/context | 风险、建议、下一步 | `list` / `process` |

## HTML 落地要求

- 顶部使用简洁结论带，不做大封面标题。
- 使用 12 栏或近似分区布局，主洞察最大，KPI 和行动建议较轻。
- 所有主卡必须有 `data-card-id`。
- 来源条独立成低视觉权重区域，不要压到页脚。
- 如果出现真实图片，只能作为证据或氛围侧栏，不得抢走主洞察锚点。

## 自检问题

1. 3 秒内是否能读出结论？
2. 30 秒内是否能看懂证据链？
3. 是否明确告诉观众下一步该做什么？
4. 如果删掉装饰，事实和建议是否仍然完整？