# XLSX 最小可执行示例

## 文件

- `sample.csv`：示例输入
- `../scripts/csv_to_xlsx_example.py`：CSV 转 XLSX + 结构样式检查脚本

## 运行

```bash
python3 scripts/csv_to_xlsx_example.py \
  --input examples/sample.csv \
  --output examples/sample.xlsx \
  --report examples/sample.style-report.json
```

## 说明

- 脚本按顺序尝试：`openpyxl` → **内置 OOXML 兜底（零依赖）**
- 即使未安装 `openpyxl`，也可生成最小合法 `.xlsx`
- 检查项包括：
  - `xl/workbook.xml`、`xl/worksheets/sheet1.xml`、`xl/styles.xml` 是否存在
  - 工作簿是否包含至少一个 sheet
  - 首行是否应用了 header 样式（style index = 1）
  - 基本数据行数量是否大于等于 2（含表头）
