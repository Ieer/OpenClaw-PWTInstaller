# DOCX 最小可执行示例

## 文件

- `sample.md`：示例输入（含标题、段落、无序/有序列表）
- `../scripts/md_to_docx_example.py`：转换与样式检查脚本

## 运行

```bash
python3 scripts/md_to_docx_example.py \
  --input examples/sample.md \
  --output examples/sample.docx \
  --report examples/sample.style-report.json
```

## 说明

- 脚本按顺序尝试：`pandoc` → `python-docx` → **内置 OOXML 兜底（零依赖）**
- 即使未安装 `pandoc` / `python-docx`，也可用内置兜底生成最小合法 `.docx`
- 样式检查会验证：
  - `word/document.xml`、`word/styles.xml`、`word/_rels/document.xml.rels` 是否存在
  - 是否检测到 `Heading*` 风格
  - 是否检测到列表风格或编号属性（`numPr`）