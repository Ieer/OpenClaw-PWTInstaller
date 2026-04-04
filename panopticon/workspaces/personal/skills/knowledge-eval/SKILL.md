# SKILL.md

## Trigger

- 当任务包含“评估 / 是否取消 / 是否支付 / 是否继续订阅 / 是否执行”时
- 当需要对预算、订阅、行程、个人事务做正式判断时
- 当输出需要“结论 + 依据 + 限制 + 下一步”时

## Steps

1. 先整理任务目标、预算/时间/授权边界。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出限制与待确认项，不直接执行不可逆动作。
5. 再输出 personal 风格的待办、优先级、Review Gate。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 支付、退款、取消订阅、改行程、删除重要资料等不可逆动作一律先 Review。