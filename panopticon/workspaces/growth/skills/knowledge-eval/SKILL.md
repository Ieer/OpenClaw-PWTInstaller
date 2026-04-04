# SKILL.md

## Trigger

- 当任务包含“实验是否继续 / 渠道是否投放 / 漏斗哪里有问题 / 文案是否上线 / 风险护栏”时
- 当需要对实验、漏斗、投放策略做正式判断时
- 当输出需要“建议 + 证据 + 护栏指标 + 下一步”时

## Steps

1. 先整理实验目标、受众、成功指标、护栏指标、预算与风险等级。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出证据不足与需要补的数据，不直接建议上线/投放。
5. 再输出 growth 风格结论：建议动作、成功指标、护栏、停止条件。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 发布、投放、群发、改线上实验开关、涉及费用/合规/隐私的动作一律先 Review。