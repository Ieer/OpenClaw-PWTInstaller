#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18910}"
AUTH_TOKEN="${MC_API_TOKEN:-${AUTH_TOKEN:-}}"

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

require_ok_health() {
  local resp
  resp="$(curl -sS "$BASE_URL/health")"
  python3 - <<'PY' "$resp"
import json, sys
obj = json.loads(sys.argv[1])
if not obj.get("ok"):
    raise SystemExit("health is not ok")
print("health_ok=true")
PY
}

main() {
  require_ok_health

  local ts unit_key common_tag create_payload create_resp unit_id
  ts="$(date +%Y%m%d%H%M%S)"
  unit_key="acceptance-unit-${ts}"
  common_tag="acceptance-minimal"

  echo "[1/4] create unit"
  create_payload="$(cat <<JSON
{
  "unit_key": "${unit_key}",
  "title": "Acceptance Unit ${ts}",
  "content": "This is a minimal acceptance knowledge unit.",
  "tags": ["${common_tag}", "ops"],
  "agent_scope": ["metrics"],
  "risk_level": "high",
  "status": "active",
  "meta": {"from": "acceptance-test"}
}
JSON
)"
  create_resp="$(curl_json POST "$BASE_URL/v1/knowledge/units" "$create_payload")"
  unit_id="$(python3 - <<'PY' "$create_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(obj["id"])
PY
)"
  python3 - <<'PY' "$create_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"unit_id={obj['id']} unit_key={obj['unit_key']} risk={obj['risk_level']}")
PY

  echo "[2/4] write validation"
  local expires_at valid_payload valid_resp
  expires_at="$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc)+timedelta(days=7)).isoformat().replace('+00:00','Z'))
PY
)"
  valid_payload="$(cat <<JSON
{
  "unit_id": "${unit_id}",
  "validator": "qa-acceptance",
  "validation_status": "approved",
  "expires_at": "${expires_at}",
  "confidence": 0.95,
  "notes": "acceptance validation"
}
JSON
)"
  valid_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validations" "$valid_payload")"
  python3 - <<'PY' "$valid_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"validation_id={obj['id']} status={obj['validation_status']} expires_at={obj.get('expires_at')}")
PY

  echo "[3/4] resolve"
  local resolve_payload resolve_resp
  resolve_payload="$(cat <<JSON
{
  "task": "acceptance flow",
  "agent_slug": "metrics",
  "risk_level": "high",
  "tags": ["${common_tag}"],
  "limit": 5
}
JSON
)"
  resolve_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve" "$resolve_payload")"
  python3 - <<'PY' "$resolve_resp" "$unit_id"
import json, sys
obj = json.loads(sys.argv[1])
unit_id = sys.argv[2]
ids = [it["unit"]["id"] for it in obj.get("items", [])]
contains = unit_id in ids
print(f"resolve_total={obj.get('total', 0)} resolved_contains_unit={str(contains).lower()}")
if not contains:
    raise SystemExit("resolve did not return the created unit")
PY

  echo "[4/4] feedback + summary"
  local fb_payload fb_resp summary_resp
  fb_payload="$(cat <<JSON
{
  "unit_id": "${unit_id}",
  "feedback_type": "usage",
  "agent": "metrics",
  "severity": "info",
  "payload": {"source": "acceptance", "note": "minimal flow ok"}
}
JSON
)"
  fb_resp="$(curl_json POST "$BASE_URL/v1/knowledge/feedback" "$fb_payload")"
  python3 - <<'PY' "$fb_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"feedback_id={obj['id']} type={obj['feedback_type']} agent={obj.get('agent')}")
PY

  summary_resp="$(curl_json GET "$BASE_URL/v1/knowledge/feedback/summary?days=7")"
  python3 - <<'PY' "$summary_resp"
import json, sys
arr = json.loads(sys.argv[1])
counts = {item["feedback_type"]: item["count"] for item in arr}
print(f"summary_usage_count={counts.get('usage', 0)}")
PY

  echo "ACCEPTANCE_UNIT_ID=${unit_id}"
  echo "ACCEPTANCE_FLOW_OK=true"
}

main "$@"
