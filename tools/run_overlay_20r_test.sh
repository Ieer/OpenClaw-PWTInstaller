#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

API_URL="${MISSION_CONTROL_API_URL:-http://127.0.0.1:18910}"
AGENT="${OVERLAY_TEST_AGENT:-nox}"
ROUNDS="${OVERLAY_TEST_ROUNDS:-20}"
UI_TICK_MS="${OVERLAY_TEST_UI_TICK_MS:-1000}"
GAP_MS="${OVERLAY_TEST_GAP_MS:-120}"

python tools/overlay_20r_test.py \
  --api-url "$API_URL" \
  --agent "$AGENT" \
  --rounds "$ROUNDS" \
  --ui-tick-ms "$UI_TICK_MS" \
  --gap-ms "$GAP_MS"
