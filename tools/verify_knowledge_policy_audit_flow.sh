#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18910}"
AUTH_TOKEN="${MC_API_TOKEN:-${AUTH_TOKEN:-}}"
USB_ROOT="${USB_KNOWLEDGE_ROOT:-/media/pi/4A21-0000/knowledge-sources}"

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
  local ts rel_path abs_path import_resp source_id chunk_resp
  ts="$(date +%Y%m%d%H%M%S)"
  rel_path="incoming/policy-audit-${ts}.md"
  abs_path="$USB_ROOT/$rel_path"

  mkdir -p "$(dirname "$abs_path")"
  cat > "$abs_path" <<'EOF'
# Policy Audit Test

This source is for source-to-units chunk pipeline validation.

Section 1: metrics operations and handoff context.

Section 2: high-risk workflows require strict validations.

Section 3: resolve audit should record selected source and reject reasons.
EOF

  import_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/import" "{\"source_type\":\"file\",\"title\":\"Policy Audit Test\",\"relative_path\":\"$rel_path\",\"owner\":\"qa-policy-audit\",\"version_label\":\"policy-audit\"}")"
  source_id="$(python3 - <<'PY' "$import_resp"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"

  chunk_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/$source_id/chunk" '{"chunk_chars":120,"chunk_overlap":10,"max_chunks":10,"risk_level":"high","tags":["policy-audit"],"agent_scope":["metrics"],"owner":"qa-policy-audit"}')"
  python3 - <<'PY' "$chunk_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"chunk_created={obj['created']} chunk_total={obj['chunks_total']} source_id={obj['source_id']}")
if int(obj.get("created", 0)) < 1:
    raise SystemExit("chunk pipeline did not create any new unit")
PY

  local policy_resp high_policy_payload strict_payload
  policy_resp="$(curl_json GET "$BASE_URL/v1/knowledge/validation-policy")"
  high_policy_payload="$(python3 - <<'PY' "$policy_resp"
import json, sys
arr = json.loads(sys.argv[1])
p = next((item for item in arr if item.get("risk_level") == "high"), None)
if not p:
    raise SystemExit("high risk policy not found")
out = {
    "strict_mode": bool(p.get("strict_mode", False)),
    "require_validation": bool(p.get("require_validation", True)),
    "require_approved": bool(p.get("require_approved", True)),
    "require_not_expired": bool(p.get("require_not_expired", True)),
    "min_confidence": p.get("min_confidence"),
    "max_validation_age_days": p.get("max_validation_age_days"),
}
print(json.dumps(out, separators=(",", ":")))
PY
)"

  cleanup_policy() {
    curl_json PUT "$BASE_URL/v1/knowledge/validation-policy/high" "$high_policy_payload" >/dev/null || true
  }
  trap cleanup_policy EXIT

  strict_payload="$(python3 - <<'PY' "$high_policy_payload"
import json, sys
payload = json.loads(sys.argv[1])
payload["strict_mode"] = True
print(json.dumps(payload, separators=(",", ":")))
PY
)"
  curl_json PUT "$BASE_URL/v1/knowledge/validation-policy/high" "$strict_payload" >/dev/null
  echo "strict_mode_enabled_for_high=true"

  local before_resp before_total first_unit_id exp validation_resp after_resp after_total audit_resp
  before_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve" '{"task":"policy-audit-before","agent_slug":"metrics","risk_level":"high","tags":["policy-audit"],"limit":5}')"
  before_total="$(python3 - <<'PY' "$before_resp"
import json, sys
print(json.loads(sys.argv[1]).get("total", 0))
PY
)"
  echo "resolve_total_before=$before_total"

  first_unit_id="$(python3 - <<'PY' "$(curl -f -sS "$BASE_URL/v1/knowledge/units?source_id=$source_id&limit=20")"
import json, sys
arr = json.loads(sys.argv[1])
print(arr[0]["id"])
PY
)"
  exp="$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc)+timedelta(days=7)).isoformat().replace('+00:00','Z'))
PY
)"
  validation_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validations" "{\"unit_id\":\"$first_unit_id\",\"validator\":\"qa-policy-audit\",\"validation_status\":\"approved\",\"expires_at\":\"$exp\",\"confidence\":0.95}")"
  python3 - <<'PY' "$validation_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"validation_id={obj['id']} status={obj['validation_status']}")
PY

  after_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve" '{"task":"policy-audit-after","agent_slug":"metrics","risk_level":"high","tags":["policy-audit"],"limit":5}')"
  after_total="$(python3 - <<'PY' "$after_resp"
import json, sys
print(json.loads(sys.argv[1]).get("total", 0))
PY
)"
  echo "resolve_total_after=$after_total"

  local strict_unit_key strict_unit_payload strict_unit_resp strict_unit_id strict_validation_resp strict_resolve_resp
  strict_unit_key="policy-audit-strict-${ts}"
  strict_unit_payload="$(cat <<JSON
{
  "unit_key": "${strict_unit_key}",
  "title": "Policy Audit Strict Unit ${ts}",
  "content": "strict mode should reject missing required validation fields",
  "tags": ["policy-audit-strict"],
  "agent_scope": ["metrics"],
  "risk_level": "high",
  "status": "active",
  "meta": {"from": "policy-audit-strict"}
}
JSON
)"
  strict_unit_resp="$(curl_json POST "$BASE_URL/v1/knowledge/units" "$strict_unit_payload")"
  strict_unit_id="$(python3 - <<'PY' "$strict_unit_resp"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"

  strict_validation_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validations" "{\"unit_id\":\"$strict_unit_id\",\"validator\":\"qa-policy-audit-strict\",\"validation_status\":\"approved\"}")"
  python3 - <<'PY' "$strict_validation_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"strict_validation_id={obj['id']} status={obj['validation_status']}")
PY

  strict_resolve_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve" '{"task":"policy-audit-strict","agent_slug":"metrics","risk_level":"high","tags":["policy-audit-strict"],"limit":5,"include_rejected":true}')"
  python3 - <<'PY' "$strict_resolve_resp"
import json, sys
obj = json.loads(sys.argv[1])
rejected = obj.get("rejected") or []
reason = rejected[0].get("reason") if rejected else "none"
print(f"strict_resolve_total={obj.get('total', 0)} strict_rejected_count={obj.get('rejected_count', 0)} strict_reason={reason}")
allowed = {
    "missing_validation_status",
    "missing_validation_expires_at",
    "missing_validation_confidence",
    "missing_validation_validated_at",
}
if reason not in allowed:
    raise SystemExit(f"strict mode reason not matched, got={reason}")
PY

  audit_resp="$(curl -f -sS "$BASE_URL/v1/knowledge/resolve/audits?limit=1")"
  python3 - <<'PY' "$audit_resp"
import json, sys
arr = json.loads(sys.argv[1])
a = arr[0]
payload = a.get("payload") or {}
rejected = payload.get("rejected") or []
print(f"audit_selected={a.get('selected_count')} audit_rejected={a.get('rejected_count')}")
print(f"audit_has_policy={'policy' in payload}")
print(f"audit_reject_reason_sample={(rejected[0].get('reason') if rejected else 'none')}")
PY

  cleanup_policy
  trap - EXIT

  echo "POLICY_AUDIT_FLOW_OK=true"
}

main "$@"
