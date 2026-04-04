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
  local ts rel_path abs_path import_resp source_id chunk_resp bundles_resp default_bundle_id
  local bundle_key bundle_resp bundle_id rule_resp rollout_resp resolve_resp unit_id audit_resp lifecycle_resp events_resp feedback_resp
  ts="$(date +%Y%m%d%H%M%S)"
  rel_path="incoming/dynamic-policy-${ts}.md"
  abs_path="$USB_ROOT/$rel_path"
  mkdir -p "$(dirname "$abs_path")"
  cat > "$abs_path" <<'EOF'
# Dynamic Policy Resolve Sample

This sample is used to verify dynamic validation policy rules, rollout targeting, and lifecycle actions.

The content is intentionally high-risk but should be let through by a targeted canary policy bundle.
EOF

  import_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/import" "{\"source_type\":\"wiki\",\"title\":\"Dynamic Policy Sample\",\"relative_path\":\"$rel_path\",\"owner\":\"qa-dynamic-policy\",\"version_label\":\"dynamic-policy\"}")"
  source_id="$(python3 - <<'PY' "$import_resp"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"

  chunk_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/$source_id/chunk" '{"chunk_chars":180,"chunk_overlap":20,"max_chunks":10,"risk_level":"high","tags":["dynamic-policy"],"agent_scope":["metrics"],"owner":"qa-dynamic-policy"}')"
  python3 - <<'PY' "$chunk_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"dynamic_chunk_created={obj['created']} chunks_total={obj['chunks_total']}")
if int(obj.get('created', 0)) < 1:
    raise SystemExit('dynamic policy fixture did not create units')
PY

  bundles_resp="$(curl_json GET "$BASE_URL/v1/knowledge/validation-policy/bundles")"
  default_bundle_id="$(python3 - <<'PY' "$bundles_resp"
import json, sys
bundles = json.loads(sys.argv[1])
default = next((item for item in bundles if item.get('bundle_key') == 'default-v1'), None)
if not default:
    raise SystemExit('default-v1 bundle not found')
print(default['id'])
PY
)"
  echo "default_bundle_id=$default_bundle_id"

  bundle_key="canary-dynamic-${ts}"
  bundle_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/bundles" "{\"bundle_key\":\"$bundle_key\",\"description\":\"canary dynamic bundle\",\"is_default\":false,\"enabled\":true}")"
  bundle_id="$(python3 - <<'PY' "$bundle_resp"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"
  echo "bundle_id=$bundle_id bundle_key=$bundle_key"

  rule_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/rules" "{\"bundle_id\":\"$bundle_id\",\"rule_key\":\"high-metrics-wiki\",\"risk_level\":\"high\",\"task_pattern\":\"*dynamic-policy*\",\"agent_slug\":\"metrics\",\"source_type\":\"wiki\",\"priority\":250,\"enabled\":true,\"strict_mode\":false,\"require_validation\":false,\"require_approved\":false,\"require_not_expired\":false,\"description\":\"dynamic policy canary rule\"}")"
  python3 - <<'PY' "$rule_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"rule_id={obj['id']} risk_level={obj['risk_level']} priority={obj['priority']}")
PY

  rollout_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/rollouts" "{\"bundle_id\":\"$bundle_id\",\"rollout_key\":\"metrics-wiki-full\",\"target_agent_slug\":\"metrics\",\"target_source_type\":\"wiki\",\"task_pattern\":\"*dynamic-policy*\",\"priority\":250,\"enabled\":true,\"rollout_mode\":\"full\"}")"
  python3 - <<'PY' "$rollout_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"rollout_id={obj['id']} rollout_mode={obj['rollout_mode']}")
PY

  resolve_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve" '{"task":"dynamic-policy canary check","agent_slug":"metrics","source_type":"wiki","risk_level":"high","tags":["dynamic-policy"],"limit":5,"include_rejected":true}')"
  unit_id="$(python3 - <<'PY' "$resolve_resp" "$bundle_key"
import json, sys
obj = json.loads(sys.argv[1])
bundle_key = sys.argv[2]
payload = obj.get('items') or []
if int(obj.get('total', 0)) < 1:
    raise SystemExit('resolve returned no items under dynamic policy canary')
print(payload[0]['unit']['id'])
PY
)"
  echo "resolved_unit_id=$unit_id"

  audit_resp="$(curl_json GET "$BASE_URL/v1/knowledge/resolve/audits?limit=20")"
  python3 - <<'PY' "$audit_resp" "$bundle_key"
import json, sys
arr = json.loads(sys.argv[1])
bundle_key = sys.argv[2]
match = next((item for item in arr if (item.get('payload') or {}).get('policy_metadata', {}).get('bundle_key') == bundle_key), None)
if not match:
    raise SystemExit('resolve audit for dynamic bundle not found')
payload = match.get('payload') or {}
meta = payload.get('policy_metadata') or {}
print(f"policy_source={meta.get('policy_source')} bundle_key={meta.get('bundle_key')} rollout_key={meta.get('rollout_key')}")
if meta.get('policy_source') != 'dynamic_rule':
    raise SystemExit('resolve audit did not use dynamic_rule policy source')
if meta.get('bundle_key') != bundle_key:
    raise SystemExit('resolve audit bundle_key mismatch')
PY

  lifecycle_resp="$(curl_json POST "$BASE_URL/v1/knowledge/units/$unit_id/lifecycle" '{"action":"demote","actor":"qa-dynamic-policy","payload":{"reason":"lifecycle verification"}}')"
  python3 - <<'PY' "$lifecycle_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"lifecycle_stage_after_demote={obj['lifecycle_stage']}")
if obj.get('lifecycle_stage') != 'deprecated':
    raise SystemExit('demote did not set lifecycle_stage=deprecated')
PY

  events_resp="$(curl_json GET "$BASE_URL/v1/knowledge/units/$unit_id/lifecycle-events?limit=10")"
  python3 - <<'PY' "$events_resp"
import json, sys
arr = json.loads(sys.argv[1])
actions = [item['action'] for item in arr]
print(f"lifecycle_events={actions}")
if 'demote' not in actions:
    raise SystemExit('lifecycle demote event not found')
PY

  feedback_resp="$(curl_json POST "$BASE_URL/v1/knowledge/feedback" "{\"unit_id\":\"$unit_id\",\"feedback_type\":\"promotion\",\"agent\":\"metrics\",\"severity\":\"info\",\"payload\":{\"reason\":\"feedback lifecycle verification\"}}")"
  python3 - <<'PY' "$feedback_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"feedback_type={obj['feedback_type']} feedback_id={obj['id']}")
PY

  echo "DYNAMIC_POLICY_ROLLOUT_FLOW_OK=true"
}

main "$@"