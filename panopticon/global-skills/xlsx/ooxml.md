# Office Open XML Technical Reference for Excel (XLSX)

**Important: Read this entire document before starting.** XLSX editing must preserve workbook relationships, sheet references, style indexes, and shared string consistency. Invalid edits can make Excel fail to open the file.

## Technical Guidelines

### Schema compliance essentials
- Keep namespace declarations intact (`x`, `r`, etc.)
- Preserve required element ordering in workbook/worksheet XML
- Do not delete IDs referenced by other parts (`sheetId`, `r:id`, style index `s`)
- Update relationship files when adding/removing sheets or parts
- Keep `sharedStrings.xml` count/uniqueCount aligned with actual string entries

### Coordinates and ranges
- Cell reference format: `A1`, `B2`, `AA10`
- Range format: `A1:C20`
- Keep `dimension` (`<dimension ref="..."/>`) consistent with actual populated area where possible

## Workbook Structure

### Main workbook
```xml
<!-- xl/workbook.xml -->
<workbook>
  <sheets>
    <sheet name="Data" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
```

### Workbook relationships
```xml
<!-- xl/_rels/workbook.xml.rels -->
<Relationships>
  <Relationship Id="rId1" Type=".../worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type=".../styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type=".../sharedStrings" Target="sharedStrings.xml"/>
</Relationships>
```

### Worksheet basics
```xml
<!-- xl/worksheets/sheet1.xml -->
<worksheet>
  <dimension ref="A1:C10"/>
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
    </row>
    <row r="2">
      <c r="A2"><v>123</v></c>
      <c r="B2"><f>SUM(A2:A10)</f></c>
    </row>
  </sheetData>
</worksheet>
```

### Shared strings
```xml
<!-- xl/sharedStrings.xml -->
<sst count="4" uniqueCount="3">
  <si><t>Name</t></si>
  <si><t>Value</t></si>
  <si><t>Total</t></si>
</sst>
```

### Styles
```xml
<!-- xl/styles.xml -->
<styleSheet>
  <fonts count="2">...</fonts>
  <fills count="2">...</fills>
  <borders count="1">...</borders>
  <cellStyleXfs count="1">...</cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" applyFont="1"/>
  </cellXfs>
</styleSheet>
```

## High-Risk Areas Checklist

### 1) Sheet references
- `workbook.xml` sheet `r:id` must exist in `workbook.xml.rels`
- `sheetId` should remain unique and stable when possible

### 2) Cell styles
- `c[@s]` style index must be within `cellXfs` bounds
- Avoid deleting style entries still referenced by cells

### 3) Shared strings
- For cells with `t="s"`, `<v>` index must exist in `sharedStrings.xml`
- Keep `count` and `uniqueCount` correct

### 4) Formulas
- Verify references after row/column insertion/deletion
- Avoid stale cached values when bulk editing formula cells

## Editing Playbook (Recommended)

1. Unpack XLSX
2. Snapshot key files before edit:
   - `xl/workbook.xml`
   - `xl/_rels/workbook.xml.rels`
   - `xl/worksheets/sheet*.xml`
   - `xl/styles.xml`
   - `xl/sharedStrings.xml`
3. Apply minimal, localized edits
4. Validate references:
   - workbook `r:id` ↔ rels targets
   - cell style indexes ↔ `cellXfs`
   - shared string indexes ↔ `sst` entries
5. Repack and open in Excel-compatible viewer for smoke test

## Validation Commands

```bash
# Unpack
python3 {baseDir}/../pptx/ooxml/scripts/unpack.py input.xlsx ./workspace/unpacked

# Validate (if validator supports XLSX profile)
python3 {baseDir}/../pptx/ooxml/scripts/validate.py ./workspace/unpacked --type xlsx

# Pack
python3 {baseDir}/../pptx/ooxml/scripts/pack.py ./workspace/unpacked output.xlsx
```

## Common Failures and Fixes

| Symptom | Root Cause | Fix |
|---|---|---|
| Excel says workbook is corrupted | invalid relationship or XML order | restore relationship mapping and schema order |
| Cells show wrong text | broken shared string index | rebuild `sharedStrings.xml` and indexes |
| Formatting lost or wrong | invalid style index `s` | fix `s` references and `cellXfs` entries |
| Formula errors (`#REF!`) | range references broken after edits | recalculate/update formula refs |
| Missing sheet tab | `workbook.xml` and rels out of sync | re-link `sheet` `r:id` to worksheet target |

## Minimal Safety Rules

- Edit one concern at a time (data, then formulas, then style)
- Never bulk-reformat all XML without clear need
- Keep backup snapshots of critical parts
- Prefer deterministic scripts for repeatable updates
