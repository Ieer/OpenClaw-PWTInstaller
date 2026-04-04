#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18910}"
AUTH_TOKEN="${MC_API_TOKEN:-${AUTH_TOKEN:-}}"
USB_ROOT="${USB_KNOWLEDGE_ROOT:-/media/pi/4A21-0000/knowledge-sources}"
WORK_DIR="${WORK_DIR:-/tmp/knowledge-ocr-fixtures}"
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
from PIL import Image, ImageDraw, ImageFont
import sys

work_dir = Path(sys.argv[1])
work_dir.mkdir(parents=True, exist_ok=True)

font = None
for candidate in [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
]:
    path = Path(candidate)
    if path.exists():
        font = ImageFont.truetype(str(path), 42)
        break
if font is None:
    font = ImageFont.load_default()

image = Image.new('RGB', (1400, 320), 'white')
draw = ImageDraw.Draw(image)
text = 'OCR SAMPLE TEXT FOR CHUNK FLOW'
draw.text((60, 120), text, fill='black', font=font)
image_path = work_dir / 'ocr-sample.png'
image.save(image_path)

pdf_path = work_dir / 'ocr-scan-sample.pdf'
image.convert('RGB').save(pdf_path, 'PDF', resolution=150.0)
PY

  local ts image_rel image_abs image_import image_source_id image_chunk image_get
  local pdf_rel pdf_abs pdf_import pdf_source_id pdf_chunk pdf_get
  ts="$(date +%Y%m%d%H%M%S)"

  image_rel="incoming/ocr-sample-${ts}.png"
  image_abs="$USB_ROOT/$image_rel"
  cp "$WORK_DIR/ocr-sample.png" "$image_abs"
  image_import="$(curl_json POST "$BASE_URL/v1/knowledge/sources/import" "{\"source_type\":\"file\",\"title\":\"OCR Image Sample\",\"relative_path\":\"$image_rel\",\"owner\":\"qa-ocr\",\"version_label\":\"ocr-image\"}")"
  image_source_id="$(python3 - <<'PY' "$image_import"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"
  image_chunk="$(curl_json POST "$BASE_URL/v1/knowledge/sources/$image_source_id/chunk" '{"chunk_chars":120,"chunk_overlap":10,"max_chunks":10,"risk_level":"normal","tags":["ocr","image"],"agent_scope":["metrics"],"owner":"qa-ocr","ocr_enabled":true,"ocr_languages":"eng","max_pdf_pages":2}')"
  python3 - <<'PY' "$image_chunk"
import json, sys
obj = json.loads(sys.argv[1])
print(f"ocr_image_created={obj['created']} chunks_total={obj['chunks_total']}")
if int(obj.get('created', 0)) < 1:
    raise SystemExit('image OCR did not create any chunk')
PY
  image_get="$(curl -f -sS "$BASE_URL/v1/knowledge/sources/$image_source_id")"
  python3 - <<'PY' "$image_get"
import json, sys
obj = json.loads(sys.argv[1])
meta = obj.get('meta') or {}
print(f"ocr_image_parser={meta.get('parser')} parse_status={meta.get('parse_status')}")
if meta.get('parser') != 'tesseract_ocr':
    raise SystemExit(f"unexpected image parser: {meta.get('parser')}")
if meta.get('ocr_languages') != 'eng':
  raise SystemExit(f"unexpected image ocr_languages: {meta.get('ocr_languages')}")
PY

  pdf_rel="incoming/ocr-scan-sample-${ts}.pdf"
  pdf_abs="$USB_ROOT/$pdf_rel"
  cp "$WORK_DIR/ocr-scan-sample.pdf" "$pdf_abs"
  pdf_import="$(curl_json POST "$BASE_URL/v1/knowledge/sources/import" "{\"source_type\":\"file\",\"title\":\"OCR Scan PDF Sample\",\"relative_path\":\"$pdf_rel\",\"owner\":\"qa-ocr\",\"version_label\":\"ocr-pdf\"}")"
  pdf_source_id="$(python3 - <<'PY' "$pdf_import"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"
  pdf_chunk="$(curl_json POST "$BASE_URL/v1/knowledge/sources/$pdf_source_id/chunk" '{"chunk_chars":120,"chunk_overlap":10,"max_chunks":10,"risk_level":"normal","tags":["ocr","scanned-pdf"],"agent_scope":["metrics"],"owner":"qa-ocr","ocr_enabled":true,"ocr_languages":"eng","max_pdf_pages":1}')"
  python3 - <<'PY' "$pdf_chunk"
import json, sys
obj = json.loads(sys.argv[1])
print(f"ocr_pdf_created={obj['created']} chunks_total={obj['chunks_total']}")
if int(obj.get('created', 0)) < 1:
    raise SystemExit('scanned PDF OCR did not create any chunk')
PY
  pdf_get="$(curl -f -sS "$BASE_URL/v1/knowledge/sources/$pdf_source_id")"
  python3 - <<'PY' "$pdf_get"
import json, sys
obj = json.loads(sys.argv[1])
meta = obj.get('meta') or {}
print(f"ocr_pdf_parser={meta.get('parser')} parse_status={meta.get('parse_status')}")
if meta.get('parser') != 'pypdf+tesseract_ocr':
    raise SystemExit(f"unexpected scanned pdf parser: {meta.get('parser')}")
if int(meta.get('max_pdf_pages') or 0) != 1:
    raise SystemExit(f"unexpected max_pdf_pages: {meta.get('max_pdf_pages')}")
PY

  local metrics_resp
  metrics_resp="$(curl_json GET "$BASE_URL/v1/knowledge/resolve/metrics?days=7&top_reasons=5")"
  python3 - <<'PY' "$metrics_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"ocr_fallback_count={obj.get('ocr_fallback_count')} ocr_failure_rate={obj.get('ocr_failure_rate')} ocr_page_truncation_count={obj.get('ocr_page_truncation_count')}")
required = ['total_parsed_sources', 'ocr_fallback_count', 'ocr_failure_count', 'ocr_failure_rate', 'ocr_page_truncation_count']
missing = [key for key in required if key not in obj]
if missing:
    raise SystemExit(f"metrics missing OCR keys: {missing}")
PY

  echo "OCR_FLOW_OK=true"
}

main "$@"
