#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18910}"
AUTH_TOKEN="${MC_API_TOKEN:-${AUTH_TOKEN:-}}"
USB_ROOT="${USB_KNOWLEDGE_ROOT:-/media/pi/4A21-0000/knowledge-sources}"
WORK_DIR="${WORK_DIR:-/tmp/knowledge-multiformat-fixtures}"
PYTHON_BIN="${PYTHON_BIN:-/home/pi/OpenClaw-PWTInstaller/.venv/bin/python}"

curl_json() {
  local method="$1"
  local url="$2"
  local data="${3:-}"
  local -a args
  args=(-f -sS -X "$method" "$url" -H "Content-Type: application/json")
  if [[ -n "$AUTH_TOKEN" ]]; then
    args+=(-H "Authorization: Bearer $AUTH_TOKEN")
  fi
  if [[ -n "$data" ]]; then
    args+=(-d "$data")
  fi
  curl "${args[@]}"
}

main() {
  mkdir -p "$WORK_DIR" "$USB_ROOT/incoming"

  "$PYTHON_BIN" - <<'PY' "$WORK_DIR"
from pathlib import Path
from docx import Document
from pptx import Presentation
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
import sys

work_dir = Path(sys.argv[1])
work_dir.mkdir(parents=True, exist_ok=True)

word_path = work_dir / 'sample.docx'
doc = Document()
doc.add_heading('Sample DOCX', level=1)
doc.add_paragraph('This is a docx extraction sample for chunk verification.')
doc.save(word_path)

pptx_path = work_dir / 'sample.pptx'
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = 'Sample PPTX'
slide.placeholders[1].text = 'This is a pptx extraction sample for chunk verification.'
prs.save(pptx_path)

xlsx_path = work_dir / 'sample.xlsx'
wb = Workbook()
ws = wb.active
ws.title = 'Sheet1'
ws['A1'] = 'sample'
ws['B1'] = 'xlsx'
ws['A2'] = 'chunk'
ws['B2'] = 'verification'
wb.save(xlsx_path)

pdf_path = work_dir / 'sample.pdf'
writer = PdfWriter()
page = writer.add_blank_page(width=300, height=200)
content = DecodedStreamObject()
content.set_data(b'BT /F1 12 Tf 36 120 Td (Sample PDF chunk verification text) Tj ET')
content_ref = writer._add_object(content)
font = DictionaryObject({NameObject('/F1'): DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})})
page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): font})
page[NameObject('/Contents')] = content_ref
with pdf_path.open('wb') as handle:
    writer.write(handle)
PY

  local formats=(docx pptx xlsx pdf)
  local ts rel_path abs_path import_resp source_id chunk_resp
  ts="$(date +%Y%m%d%H%M%S)"

  for ext in "${formats[@]}"; do
    rel_path="incoming/multiformat-${ts}.${ext}"
    abs_path="$USB_ROOT/$rel_path"
    cp "$WORK_DIR/sample.${ext}" "$abs_path"

    import_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/import" "{\"source_type\":\"file\",\"title\":\"MultiFormat ${ext}\",\"relative_path\":\"$rel_path\",\"owner\":\"qa-multiformat\",\"version_label\":\"multiformat\"}")"
    source_id="$(python3 - <<'PY' "$import_resp"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"

    chunk_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/$source_id/chunk" "{\"chunk_chars\":120,\"chunk_overlap\":10,\"max_chunks\":10,\"risk_level\":\"normal\",\"tags\":[\"multiformat\",\"${ext}\"],\"agent_scope\":[\"metrics\"],\"owner\":\"qa-multiformat\"}")"
    python3 - <<'PY' "$chunk_resp" "$ext"
import json, sys
obj = json.loads(sys.argv[1])
ext = sys.argv[2]
print(f"format={ext} created={obj['created']} chunks_total={obj['chunks_total']}")
if int(obj.get('created', 0)) < 1:
    raise SystemExit(f'{ext} did not create any chunk')
PY
  done

  echo "MULTIFORMAT_CHUNK_FLOW_OK=true"
}

main "$@"
