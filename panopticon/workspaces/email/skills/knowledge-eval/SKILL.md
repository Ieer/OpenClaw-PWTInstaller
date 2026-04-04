# SKILL.md

## Trigger

- 当任务包含“是否发送 / 如何回复 / 风险措辞 / 承诺边界 / 是否需要跟进”时
- 当需要对邮件策略、回复口径、外发风险做正式判断时
- 当输出需要“建议 + 依据 + 风险 + 下一步”时

## Steps

1. 先整理收件人、目标、语气、可承诺边界与风险等级。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出待确认项，不代替用户做外发承诺。
5. 再输出 email 风格结论：建议回复方向、风险、跟进动作、是否需要 Review。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 任何发送、回复、转发、对外承诺、包含敏感信息的邮件一律先 Review。