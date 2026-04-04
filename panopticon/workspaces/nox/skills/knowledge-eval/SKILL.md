# SKILL.md

## Trigger

- 当任务包含“评估 / 判断 / 建议 / 影响分析 / 是否继续 / 风险 / 依据”时
- 当需要对 roadmap、发布影响、产品方案做正式结论时
- 当输出需要“结论 + 依据 + 限制”三段结构时

## Steps

1. 先整理任务目标、约束、风险等级。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出限制与下一步，不伪造依据。
5. 再输出 nox 风格的 roadmap / 影响评估 / 建议动作。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 若结论涉及对外发布、生产变更、不可逆动作，必须进入 Review。