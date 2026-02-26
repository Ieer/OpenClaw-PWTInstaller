````skill
---
name: docx
description: "Word document creation, editing, and analysis. When Claude needs to work with documents (.docx files) for: (1) Creating structured reports/specs/contracts, (2) Editing existing content while preserving styles, (3) Working with headings/tables/lists/sections, (4) Handling comments/track-changes/footnotes, or any other document tasks"
license: Proprietary. Inherit repository-level license unless overridden
---

# Overview

When creating or modifying Word documents, prioritize structure correctness, style consistency, and OOXML integrity.

## docx Workflow

1. [Reading and analyzing content](#reading-and-analyzing-content).
2. **MANDATORY - READ ENTIRE FILE**: Read [`ooxml.md`](ooxml.md) completely from start to finish. **NEVER set any range limits when reading this file.** Read full content for schema rules, relationship updates, and safety checks before editing OOXML.
3. Choose generation/editing mode:
   - **Fast drafting (preferred for new docs)**: draft in Markdown/plain text, then convert to `.docx` with a converter available in environment.
   - **Precise editing (preferred for existing docs with strict format)**: unpack `.docx` and edit XML directly.
4. If using OOXML path:
   - Unpack, inspect `word/document.xml` + style/numbering/relations files
   - Apply minimal XML changes (keep element order and namespace correctness)
   - Repack and validate document openability
5. **Visual/semantic validation**:
   - Ensure heading hierarchy is continuous (`Heading 1` → `Heading 2` ...)
   - Ensure lists/numbering references are valid and not broken
   - Ensure table borders/widths and page breaks do not cause readability issues
   - Ensure comments/track changes (if any) remain structurally valid

## Reading and analyzing content

### Text extraction
If you only need textual content, convert `.docx` to Markdown first:

```bash
python -m markitdown path-to-file.docx
```

### Raw XML access
You need raw XML access for: comments, tracked changes, styles inheritance, numbering definitions, section/page setup, headers/footers, footnotes/endnotes, and relationship-level fixes.

#### Unpacking a file
```bash
python3 {baseDir}/../pptx/ooxml/scripts/unpack.py <office_file> <output_dir>
```

**Note**: `{baseDir}` means this skill root (directory containing `SKILL.md`).

#### Key DOCX file structures
- `word/document.xml` - 主文档正文
- `word/styles.xml` - 段落/字符/表格样式定义
- `word/numbering.xml` - 编号与多级列表
- `word/comments.xml` - 批注
- `word/footnotes.xml`, `word/endnotes.xml` - 脚注/尾注
- `word/header*.xml`, `word/footer*.xml` - 页眉页脚
- `word/_rels/document.xml.rels` - 主文档资源关系
- `_rels/.rels` 与 `[Content_Types].xml` - 包关系与内容类型

### Design principles for document authoring

**CRITICAL**: Before writing content, identify document intent and choose structure first.

1. **Document type**: proposal / report / SOP / contract / memo / PRD
2. **Audience**: executives / legal / engineering / operations / external clients
3. **Readability strategy**: short paragraphs, layered headings, purposeful tables
4. **Change policy**: if editing existing file, preserve style IDs and numbering IDs unless absolutely necessary

**Requirements**:
- ✅ 先设计“目录层级 + 章节职责”，再填正文
- ✅ 中文正文优先使用 CJK 友好字体（由模板样式决定，不在正文里硬编码）
- ✅ 列表必须用真实编号/项目符号（不要手工输入 `1.` 或 `-` 伪列表）
- ✅ 表格用于结构化信息，不堆砌长段落
- ✅ 大文档优先“分节 + 统一样式”，避免局部手工格式漂移

### Common structure patterns

- **标准报告**: 封面 → 摘要 → 背景 → 分析 → 结论 → 附录
- **SOP/操作手册**: 目的 → 适用范围 → 术语 → 步骤 → 异常处理 → 记录
- **产品文档**: 目标 → 需求范围 → 用户场景 → 交互/流程 → 验收标准
- **合同草案**: 定义 → 权责 → 交付/验收 → 费用 → 合规 → 争议处理

## Use Cases

- 从零创建结构化 `.docx` 文档（报告/方案/规范）
- 批量修订既有 `.docx`（章节重排、样式统一、术语替换）
- 解析 OOXML 做高级编辑（批注、修订、脚注、页眉页脚）
- 修复文档结构损坏（关系断链、编号异常、内容类型缺失）

## Run

```bash
# 解包（用于精确编辑）
python3 {baseDir}/../pptx/ooxml/scripts/unpack.py input.docx ./workspace/unpacked

# 可选：结构校验
python3 {baseDir}/../pptx/ooxml/scripts/validate.py ./workspace/unpacked --type docx

# 打包回 docx
python3 {baseDir}/../pptx/ooxml/scripts/pack.py ./workspace/unpacked output.docx
```

## Inputs

- 原始文档或文档草稿（可为 Markdown/纯文本）
- 模板或样式约束（字体、标题层级、页边距、公司规范）
- 编辑意图（增量修改 / 全量重写 / 结构修复）
- 可选：审阅要求（是否保留修订、批注规则）

## Outputs

- 生成或更新后的 `.docx` 文件
- 必要时的解包目录与结构校验结果
- 结构变更说明（章节、列表、样式、关系）

## Safety

- 严禁直接破坏样式与编号的引用关系（`w:pStyle` / `w:numId`）
- 修改关系文件后必须同步校验引用完整性
- 涉及合同/政策类文档时，优先保持原语义，不擅自改写法律措辞
- 保留可回退中间产物（解包目录与变更脚本）

## Version

- Template-Version: 1.0
- Last-Updated: 2026-02-26

````