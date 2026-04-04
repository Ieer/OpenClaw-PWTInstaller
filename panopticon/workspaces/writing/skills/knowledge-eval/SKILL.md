# SKILL.md

## Trigger

- 当任务包含“资料是否足够 / 观点能不能写 / 大纲怎么立 / 哪些断言需要来源 / 是否可发布”时
- 当需要对写作 brief、来源充分性、对外内容做正式判断时
- 当输出需要“结论 + 依据来源 + 限制 + 待核实项”时

## Steps

1. 先整理主题、受众、语气、来源要求与风险等级。
2. 运行 `scripts/run_eval_artifact.py` 发起知识评估。
3. 检查 `artifacts/<task_id>/artifact.md` 和 `artifacts/<task_id>/artifact.json`。
4. 若 `summary.status=no_hit` 或 `weak_hit`，明确写出来源不足与待核实项，不编造细节。
5. 再输出 writing 风格结论：大纲/判断、来源依据、限制、是否需要 Review。

## Output

- `artifacts/<task_id>/artifact.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/resolve-response.json`

## Review Gate

- 对外发布、署名观点、涉及隐私/合规/合同条款的内容一律先 Review。