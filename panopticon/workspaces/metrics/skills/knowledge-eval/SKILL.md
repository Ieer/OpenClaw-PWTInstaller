# SKILL.md

## Trigger

- 当任务包含“异常是否成立 / 指标怎么解释 / 是否需要升级 / 口径依据 / 风险提示”时
- 当需要对指标、归因、报表结论做正式判断时
- 当输出需要“结论 + 口径/来源 + 不确定性 + 下一步”时

## Steps

1. 先整理任务目标、指标口径、数据边界与风险等级。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出证据不足与待补数据，不伪造精确结论。
5. 再输出 metrics 风格结论：结论、口径/来源、不确定性、下一步。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 对外发布、改生产配置、删除重要文件等动作一律先 Review。