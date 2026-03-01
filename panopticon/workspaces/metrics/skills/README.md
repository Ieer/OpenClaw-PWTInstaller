# skills/README.md (metrics)

本目录放置 workspace 级技能文档（`*/SKILL.md`）。

## Skill 规范

- 触发条件：什么输入下调用该技能
- 执行流程：按步骤、可审计、可复现
- 输出规范：写入 `artifacts/<task_id>/` 与 `sources/<task_id>/`
- 风险控制：若有外部副作用，必须先进入 Review

## 最小模板

```markdown
# SKILL.md

## Trigger
- ...

## Steps
1. ...

## Output
- artifacts/<task_id>/artifact.md
- artifacts/<task_id>/artifact.json
- sources/<task_id>/...

## Review Gate
- ...
```