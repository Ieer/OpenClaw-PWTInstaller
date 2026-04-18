# PPTX 模板局部更新作者指南

> 面向要“保留原模板 / 母版 / 主题 / 页背景，只改指定页内容”的模板作者。
> 目标是把 block-level update 做成可重复、可回放、可维护的模板合同，而不是一次性人工操作。

## 1. 适用场景

- 已经有品牌模板、母版、页脚、背景纹理，不想重新生成整套 deck。
- 只需要替换少量页面中的正文、图表、表格或局部卡片。
- 希望后续多次重跑仍然能精准替换，而不是越跑越堆 shape。

## 2. CLI 最小用法

```bash
python3 scripts/svg2pptx.py ppt-output/runs/<RUN_ID>/svg \
  -o ppt-output/runs/<RUN_ID>/presentation-svg.pptx \
  --html-dir ppt-output/runs/<RUN_ID>/slides \
  --export-report ppt-output/runs/<RUN_ID>/svg-export-report.json \
  --report-path ppt-output/runs/<RUN_ID>/presentation-svg.report.json \
  --template-pptx templates/brand-deck.pptx \
  --target-slides 2,5,7
```

含义：

- `--template-pptx`：把现有 deck 作为目标模板。
- `--target-slides`：SVG 第 1、2、3 页分别替换模板中的第 2、5、7 页。
- 未命中的模板页、主题、母版、页背景、既有装饰元素全部保留。

## 3. 命名合同

### 3.1 模板作者命名

如果你希望某个模板占位区域在重跑时被精准替换，模板里对应对象应命名为：

- `BlockSlot:<block_id>:...`

例如：

- `BlockSlot:s02-anchor-1:title`
- `BlockSlot:s02-support-2:chart`

规则：

- `block_id` 必须与 planning / HTML 根节点中的 `data-card-id` 一致。
- 冒号后的尾缀仅用于作者自我说明，不参与 block 命中。

### 3.2 导出器生成的 managed 名称

导出后，系统会自动把新对象命名为：

- `Block:<block_id>:...`
- `ChartGroup:...:block=<block_id>`
- `NativeChart:...:<chart_type>:block=<block_id>`

这意味着第二次、第三次重跑时，导出器可以只删除命中的 managed 对象，而不碰未管理的模板元素。

## 4. block-level 替换语义

命中规则不是“整页清空”，而是“只删目标 block 范围内的可管理对象”：

1. 先读取 HTML / semantic sidecar 中的 `block_id`。
2. 在目标模板页中匹配 `BlockSlot:<block_id>:...` 占位对象。
3. 删除命中的旧 slot 和旧 managed shape。
4. 把新的文本、表格、图表写回该页。
5. 保留页背景、页脚、品牌装饰、未命中的既有形状。

## 5. 模板作者检查清单

- 每个可替换区域是否都有稳定 `BlockSlot:<block_id>:...` 名称。
- block 的视觉边界是否清晰，不要让一个 block 横跨整页多个层级。
- 页脚、章节编号、品牌水印是否不要命名成 `BlockSlot:`，避免被误删。
- 若模板页里已有图表占位，请单独成组，不要和页脚或装饰粘在一起。
- 同一页多个 block 时，优先保持 block 之间互不重叠。

## 6. 推荐作者工作流

1. 先在模板中给可替换区域命名 `BlockSlot:<block_id>:...`。
2. 跑一次 `svg2pptx.py --template-pptx --target-slides ...`。
3. 检查 `presentation-svg.report.json` 里的 `updated_blocks_total` 与 `template_removed_shapes_total`。
4. 再跑一次同一页更新，确认旧 managed shape 被替换而不是叠加。
5. 用 `presentation-svg.inspect.json` 检查 structured chart hit-rate 和退化情况。

## 7. 常见失败模式

### block_id 不一致

- 症状：模板页不报错，但旧内容没被替换。
- 原因：模板 slot 名称里的 `block_id` 与 HTML `data-card-id` 不一致。
- 修复：统一 planning、HTML、模板三处 block_id。

### 一个 slot 覆盖多个阅读层

- 症状：更新时连带删掉不该删的标题或页脚。
- 原因：模板作者把大范围容器整体命名为 `BlockSlot:`。
- 修复：把可替换区域拆回更细粒度的 block。

### 非 managed 元素被误认为可替换

- 症状：品牌装饰或页码在重跑后消失。
- 原因：误用 `BlockSlot:` / `Block:` / `ChartGroup:` / `NativeChart:` 前缀。
- 修复：模板自带元素不要使用 managed 命名前缀。

## 8. 验收口径

满足以下四条，才能算模板更新链路稳定：

- 指定目标页以外没有被修改。
- 同一目标页重跑后不会堆积旧 managed shape。
- 页背景、母版、主题、页脚仍完整保留。
- `presentation-svg.report.json` 与 `presentation-svg.inspect.json` 的 block / chart 统计符合预期。