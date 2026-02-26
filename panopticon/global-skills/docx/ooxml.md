# Office Open XML Technical Reference for Word (DOCX)

**Important: Read this entire document before starting.** DOCX editing must preserve schema order, relationships, and numbering/style references. Invalid edits can make Word refuse to open the file.

## Technical Guidelines

### Schema compliance essentials
- Keep namespace declarations intact (`w`, `r`, `wp`, `a`, etc.)
- Preserve element ordering required by OOXML schema
- Use `xml:space="preserve"` when text runs contain leading/trailing spaces
- Avoid deleting IDs that are referenced elsewhere (`w:numId`, `w:styleId`, relationship `r:id`)
- Add or update relationship entries when introducing media, hyperlinks, headers/footers, footnotes/endnotes

### Units and sizing
- OOXML length often uses twips: `1 pt = 20 twips`
- Common A4 page size in twips: `w=11906`, `h=16838`
- Be consistent with section properties (`w:sectPr`) when changing page setup

## Document Structure

### Main content container
```xml
<!-- word/document.xml -->
<w:document>
  <w:body>
    <w:p>...</w:p>
    <w:tbl>...</w:tbl>
    <w:sectPr>...</w:sectPr>
  </w:body>
</w:document>
```

### Paragraph and run basics
```xml
<w:p>
  <w:pPr>
    <w:pStyle w:val="Heading1"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:b/>
      <w:sz w:val="28"/>
    </w:rPr>
    <w:t>Section Title</w:t>
  </w:r>
</w:p>
```

### Lists and numbering
```xml
<w:p>
  <w:pPr>
    <w:numPr>
      <w:ilvl w:val="0"/>
      <w:numId w:val="5"/>
    </w:numPr>
  </w:pPr>
  <w:r><w:t>First list item</w:t></w:r>
</w:p>
```

**Rule**: `w:numId` must exist in `word/numbering.xml`. Never invent IDs without updating numbering definitions.

### Tables
```xml
<w:tbl>
  <w:tblPr>
    <w:tblW w:type="dxa" w:w="9000"/>
    <w:tblBorders>...</w:tblBorders>
  </w:tblPr>
  <w:tr>
    <w:tc>
      <w:p><w:r><w:t>Cell text</w:t></w:r></w:p>
    </w:tc>
  </w:tr>
</w:tbl>
```

### Hyperlinks and relationships
```xml
<w:hyperlink r:id="rId10">
  <w:r>
    <w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr>
    <w:t>Open link</w:t>
  </w:r>
</w:hyperlink>
```

When adding hyperlink/media:
1. Add node in `word/_rels/document.xml.rels`
2. Ensure content type/part path is valid
3. Reference correct `r:id` from `document.xml`

## High-Risk Areas Checklist

### 1) Styles (`word/styles.xml`)
- Keep style inheritance (`w:basedOn`) valid
- Do not delete built-in styles used by paragraphs/runs
- Prefer reusing existing style IDs over creating many near-duplicate styles

### 2) Numbering (`word/numbering.xml`)
- Maintain mapping: `abstractNum` ↔ `num`
- Reusing `numId` is safer than creating new IDs for small edits
- For multi-level lists, ensure all referenced `ilvl` levels are defined

### 3) Sections (`w:sectPr`)
- Keep page size/margins/header-footer refs consistent
- If splitting sections, verify each section has complete properties

### 4) Revision marks / comments
- Track changes elements (`w:ins`, `w:del`) can break if run boundaries are malformed
- Comment references must match entries in `word/comments.xml`

## Editing Playbook (Recommended)

1. Unpack DOCX
2. Snapshot key files before edit:
   - `word/document.xml`
   - `word/styles.xml`
   - `word/numbering.xml`
   - `word/_rels/document.xml.rels`
3. Apply minimal, localized XML edits
4. Validate references:
   - style IDs referenced by `w:pStyle` / `w:rStyle`
   - numbering IDs referenced by `w:numId`
   - relationship IDs referenced by `r:id`
5. Repack and open in Word-compatible viewer for smoke test

## Validation Commands

```bash
# Unpack
python3 {baseDir}/../pptx/ooxml/scripts/unpack.py input.docx ./workspace/unpacked

# Validate (if validator supports DOCX profile)
python3 {baseDir}/../pptx/ooxml/scripts/validate.py ./workspace/unpacked --type docx

# Pack
python3 {baseDir}/../pptx/ooxml/scripts/pack.py ./workspace/unpacked output.docx
```

## Common Failures and Fixes

| Symptom | Root Cause | Fix |
|---|---|---|
| Word says file is corrupted | invalid XML order or missing required node | revert and reapply with schema order |
| List numbering resets unexpectedly | broken `numId`/`abstractNum` mapping | repair `numbering.xml` references |
| Styles disappear | deleted or renamed styleId still referenced | restore style or update references |
| Links/images broken | missing `document.xml.rels` entry | add relationship and correct `r:id` |
| Header/footer missing | invalid section refs | fix `w:sectPr` header/footer references |

## Minimal Safety Rules

- Edit one concern at a time (structure, then style, then numbering)
- Never bulk-reformat whole XML without necessity
- Keep backups of unpacked parts before each major change
- Prefer deterministic scripts for repeated changes