````skill
---
name: xlsx
description: "Spreadsheet creation, editing, and analysis. When Claude needs to work with spreadsheets (.xlsx files) for: (1) Creating reports/tables/metrics sheets, (2) Editing existing workbook structures, (3) Managing formulas/styles/sheets, (4) Handling data validation and formatting, or any other spreadsheet tasks"
license: Proprietary. Inherit repository-level license unless overridden
---

# Overview

When creating or modifying Excel workbooks, prioritize data correctness, formula integrity, and OOXML consistency.

## xlsx Workflow

1. [Reading and analyzing content](#reading-and-analyzing-content).
2. **MANDATORY - READ ENTIRE FILE**: Read [`ooxml.md`](ooxml.md) completely from start to finish. **NEVER set any range limits when reading this file.** Read full content for relationship rules, sheet structures, and safety checks before OOXML edits.
3. Choose generation/editing mode:
   - **Fast generation (preferred for new files)**: prepare CSV/JSON structured data and generate `.xlsx`.
   - **Precise editing (preferred for strict templates)**: unpack `.xlsx` and edit workbook/sheet XML directly.
4. If using OOXML path:
   - Unpack and inspect `xl/workbook.xml`, `xl/worksheets/sheet*.xml`, `xl/styles.xml`, and rels
   - Apply minimal XML edits (preserve references and ordering)
   - Repack and verify workbook can open normally
5. **Validation**:
   - Ensure sheet relationships and IDs are consistent
   - Ensure formulas still reference valid ranges/sheets
   - Ensure style IDs used in cells exist in `styles.xml`
   - Ensure shared strings indexes match `sharedStrings.xml` when using `t="s"`

## Reading and analyzing content

### Text extraction
For quick textual extraction:

```bash
python -m markitdown path-to-file.xlsx
```

### Raw XML access
You need raw XML for: style-level edits, formula repairs, named ranges, table definitions, merged cells, data validation rules, and relationship fixes.

#### Unpacking a file
```bash
python3 {baseDir}/../pptx/ooxml/scripts/unpack.py <office_file> <output_dir>
```

**Note**: `{baseDir}` means this skill root (directory containing `SKILL.md`).

#### Key XLSX file structures
- `xl/workbook.xml` - 工作簿与 sheet 列表
- `xl/worksheets/sheet{N}.xml` - 单个工作表数据
- `xl/styles.xml` - 字体、填充、边框、单元格样式
- `xl/sharedStrings.xml` - 共享字符串池
- `xl/_rels/workbook.xml.rels` - sheet 与部件关系
- `[Content_Types].xml` - 包级内容类型声明
- `_rels/.rels` - 包根关系

### Design principles for spreadsheets

**CRITICAL**: Before generating spreadsheets, define semantic structure first.

1. **Workbook intent**: dashboard / report / raw data / model input
2. **Sheet roles**: source / transform / summary / output
3. **Data contract**: header names, types, required fields, nullable policy
4. **Change policy**: preserve formulas and named ranges when editing existing templates

**Requirements**:
- ✅ 先定义列 schema（字段名、类型、约束）再写数据
- ✅ 第一行使用明确 header，不混用注释/数据
- ✅ 公式与静态值分层（避免在同一列混杂）
- ✅ 样式仅用于可读性，不改变数据语义
- ✅ 多 sheet 文件明确输入/输出边界，避免循环引用

### Common workbook patterns

- **运营周报**: `raw_data` → `metrics` → `dashboard`
- **财务汇总**: `transactions` → `mapping` → `summary`
- **实验记录**: `samples` → `results` → `qc`
- **项目看板导出**: `tasks` → `status_pivot` → `review`

## Use Cases

- 从零生成结构化 `.xlsx`（报表、台账、汇总）
- 批量修订既有 `.xlsx`（表头统一、公式修复、sheet 重排）
- 解析 OOXML 做高级编辑（样式、合并单元格、验证规则）
- 修复结构损坏（关系断链、样式索引失效、sharedStrings 不一致）

## Run

```bash
# 解包
python3 {baseDir}/../pptx/ooxml/scripts/unpack.py input.xlsx ./workspace/unpacked

# 可选：结构校验（若校验器支持）
python3 {baseDir}/../pptx/ooxml/scripts/validate.py ./workspace/unpacked --type xlsx

# 打包回 xlsx
python3 {baseDir}/../pptx/ooxml/scripts/pack.py ./workspace/unpacked output.xlsx
```

## Inputs

- 原始数据（CSV/JSON/数据库导出）
- 列定义（字段、类型、单位、精度）
- 业务规则（公式、阈值、汇总维度）
- 可选：模板约束（sheet 名称、样式、冻结窗格）

## Outputs

- 生成或更新后的 `.xlsx` 文件
- 样式/结构检查报告（可选）
- 必要时的解包目录与差异说明

## Safety

- 严禁随意重排 sheetId 与 relationshipId
- 修改公式后必须检查引用范围与错误值（`#REF!`, `#VALUE!`）
- 使用 sharedStrings 时必须保持索引与计数一致
- 保留可回退中间产物（解包目录与脚本）

## Version

- Template-Version: 1.0
- Last-Updated: 2026-02-26

````
