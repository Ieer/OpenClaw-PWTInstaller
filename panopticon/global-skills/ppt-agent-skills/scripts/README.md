# Scripts Index

本目录包含 PPT 工作流的全部执行脚本。

## 核心调度

| 脚本 | 用途 | 调用方 |
|------|------|--------|
| `prompt_harness.py` | 模板变量填充，生成 subagent prompt | 主 agent |
| `resource_loader.py` | 资源路由器（menu 菜单 / resolve 按需加载 / images 图片清单） | subagent |

## 校验工具

| 脚本 | 用途 | 调用方 |
|------|------|--------|
| `contract_validator.py` | 合同校验（`interview` / `requirements-interview` / `search` / `search-brief` / `source-brief` / `outline` / `style` / `speech-script` / `images` / `page-review` / `delivery-manifest` / `svg-export-report` / `pptx-export-report` / `pptx-inspection`） | 主 agent |
| `planning_validator.py` | Step 4 planning JSON 单页/全量验证 | subagent 自审 + 主 agent gate |
| `milestone_check.py` | 按里程碑阶段验收 | 主 agent |
| `inspect_pptx.py` | 检查生成后 PPTX 的真实结构，识别整页图片退化，并统计 `ChartGroup:*` / `NativeChart:*` 命中（`NativeChart:*` 可为真实 PPT chart 或命名的原生组合 group） | 主 agent / 维护者 |
| `check_skill.py` | 检查 markdown / prompt / validator / 资源之间的协议漂移 | skill 作者 / 维护者 |
| `smoke_skill.py` | 跑 Step 4 的最小端到端 smoke test（validator + resource_loader + prompt_harness） | skill 作者 / 维护者 |

说明：

- `contract_validator.py style` 现已按 runtime style 合同检查 `style_id`、`style_name`、`mood_keywords`、`design_soul`、`variation_strategy`、`decoration_dna`、`css_variables`、`font_family`
- Step 5 现在先生成 `speech-script.json`，再派生 `speech-script.md`，并把 notes 写入 PNG / SVG 两份 PPTX；`milestone_check.py 5` 会同时验 `speech-script` 合同和 notes 覆盖情况
- Step 5 的 SVG 导出现在会额外产出 `svg-export-report.json`、`presentation-svg.report.json`，`milestone_check.py 5` 会再调用 `inspect_pptx.py` 生成 `presentation-svg.inspect.json` 做结构检查；若报告处于 `template_update` 模式，会额外打印 target slides、updated blocks、removed shapes，并继续输出 structured chart / `ChartGroup` hit rate 摘要
- `resource_loader.py` 的 `menu` / `resolve` 会跳过 `runtime-*` 文件；这些文件由主链定向注入
- `check_skill.py` 是维护期自检，不参与运行时调度；建议改完 `tpl` / `playbook` / `cli-cheatsheet` / Step 4 schema 示例后手动跑一次
- `smoke_skill.py` 是维护期冒烟，不参与运行时调度；它会真实调用现有 CLI，验证 Step 0 双模板按能力裁剪、Step 4 最小主链、非 `content` 页 `page-templates/` 路由、关键资源型 prompt 注入，以及 Step 5 的 speech-script 派生、speaker notes 写入、template-update block-level 替换、`sparkline` / `rating` / `timeline` / `funnel` / `radar` / `waffle` / `treemap` 原生 promotion 与 gate 验收还能接通

## 导出工具

| 脚本 | 用途 |
|------|------|
| `html_packager.py` | 生成 preview.html |
| `html2png.py` | HTML -> PNG 截图 |
| `html2svg.py` | HTML -> SVG 转换；优先使用系统 Chromium，并自动写出 `svg-export-report.json` 与每页 `*.semantic.json` 语义 sidecar（含 block/table/chart regions） |
| `png2pptx.py` | PNG -> PPTX 导出；可选消费 `--speech-script` 写入 speaker notes |
| `svg2pptx.py` | SVG -> PPTX 导出；可消费 `--html-dir` + `html2svg` sidecar 做 block-aware 文本重建、native table 提升、`comparison_bar` / `progress_bar` / `stacked_bar` 的 native chart promotion、`sparkline` / `rating` / `kpi` / `ring` / `metric_row` / `timeline` / `funnel` / `radar` / `waffle` / `treemap` 的命名原生组合 promotion，以及其余 chart-like region 的 grouped-shape fallback；同时支持 `--speech-script` 写入 speaker notes，并支持 `--template-pptx --target-slides` 对现有 PPTX 做保留主题/母版/背景的 block-level 局部改写。若模板页占位对象命名为 `BlockSlot:<block_id>:...`，只会替换命中的 block，并自动写出 `presentation-svg.report.json` |
| `speech_script_formatter.py` | `speech-script.json` -> `speech-script.md` |

## 辅助

| 脚本 | 用途 |
|------|------|
| `workflow_versions.py` | 统一 workflow/schema version 常量 |
| `speech_script.py` | speech-script 解析 / Markdown 派生 / speaker notes 读写共享辅助 |

## 依赖关系

```
prompt_harness.py       -- 独立
resource_loader.py      -- 独立
contract_validator.py   -> planning_validator.py -> workflow_versions.py
milestone_check.py      -- 独立
check_skill.py          -> planning_validator.py + prompt_harness.py
smoke_skill.py          -> planning_validator.py + resource_loader.py + prompt_harness.py
speech_script_formatter.py -> speech_script.py -> planning_validator.py
```
