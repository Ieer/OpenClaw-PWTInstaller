# SKILL.md

## Trigger

- 当任务包含“论点是否成立 / 风险是否足够小 / 是否值得继续跟踪 / 需要哪些执行前检查”时
- 当需要对晨报、论点卡片、风险清单做正式判断时
- 当输出需要“事实 + 推断 + 风险 + 待确认项”时

## Steps

1. 先整理关注标的、时间周期、风险边界与任务目标。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出证据缺口与不确定性，不给出伪确定结论。
5. 再输出 trades 风格结论：事实、推断、反证、风险、Review Gate。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 下单、转账、授权、绑定账户、导出敏感报表等任何可能影响真实资金/账户安全的动作一律先 Review。