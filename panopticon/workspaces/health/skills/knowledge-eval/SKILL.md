# SKILL.md

## Trigger

- 当任务包含“训练是否合适 / 恢复够不够 / 作息怎么调 / 风险提示 / 需要确认什么”时
- 当需要对训练、睡眠、恢复建议做正式判断时
- 当输出需要“计划 + 替代方案 + 风险提示 + 需确认项”时

## Steps

1. 先整理目标、时间/器械、禁忌、既往伤病与风险等级。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出缺失条件与不确定性，不把建议包装成诊断。
5. 再输出 health 风格结论：计划、替代方案、风险提示、Review Gate。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 强度训练、极端饮食、补剂/药物相关、涉及既往病史/禁忌的高风险建议一律先 Review。