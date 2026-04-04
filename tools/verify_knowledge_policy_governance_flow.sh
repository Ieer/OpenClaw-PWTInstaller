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
  local profile_key profile_resp profile_id bundle_key bundle_resp bundle_id rule_resp rollout_resp rollout_id resolve_resp
  local observability_resp change_resp rollback_rollout_resp rollout_list_resp rollback_bundle_resp bundle_list_resp

  ts="$(date +%Y%m%d%H%M%S)"
  rel_path="incoming/policy-governance-${ts}.md"
  abs_path="$USB_ROOT/$rel_path"
  mkdir -p "$(dirname "$abs_path")"
  cat > "$abs_path" <<'EOF'
# Policy Governance Sample

This source verifies custom ranking profile management, observability reporting, and rollback tools.

The sample contains incident triage and operational guidance keywords.
EOF

  import_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/import" "{\"source_type\":\"wiki\",\"title\":\"Policy Governance Sample\",\"relative_path\":\"$rel_path\",\"owner\":\"qa-governance\",\"version_label\":\"policy-governance\"}")"
  source_id="$(python3 - <<'PY' "$import_resp"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"

  chunk_resp="$(curl_json POST "$BASE_URL/v1/knowledge/sources/$source_id/chunk" '{"chunk_chars":180,"chunk_overlap":20,"max_chunks":10,"risk_level":"high","tags":["policy-governance"],"agent_scope":["metrics"],"owner":"qa-governance"}')"
  python3 - <<'PY' "$chunk_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"governance_chunk_created={obj['created']} chunks_total={obj['chunks_total']}")
if int(obj.get('created', 0)) < 1:
    raise SystemExit('policy governance fixture did not create units')
PY

  profile_key="governance-${ts}"
  profile_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve/ranking-profiles" "{\"profile_key\":\"$profile_key\",\"description\":\"governance custom profile\",\"enabled\":true,\"base_score\":1.1,\"lexical_weight\":0.95,\"semantic_weight\":1.15,\"tag_weight\":0.45,\"validation_confidence_weight\":0.55,\"approved_bonus\":0.6,\"preferred_bonus\":0.4,\"deprecated_penalty\":0.2}")"
  profile_id="$(python3 - <<'PY' "$profile_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(obj['id'])
PY
)"
  echo "ranking_profile_id=$profile_id profile_key=$profile_key"

  bundle_key="governance-bundle-${ts}"
  bundle_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/bundles" "{\"bundle_key\":\"$bundle_key\",\"description\":\"governance bundle\",\"is_default\":false,\"enabled\":true}")"
  bundle_id="$(python3 - <<'PY' "$bundle_resp"
import json, sys
print(json.loads(sys.argv[1])['id'])
PY
)"
  echo "bundle_id=$bundle_id bundle_key=$bundle_key"

  rule_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/rules" "{\"bundle_id\":\"$bundle_id\",\"rule_key\":\"governance-high\",\"risk_level\":\"high\",\"task_pattern\":\"*policy-governance*\",\"agent_slug\":\"metrics\",\"source_type\":\"wiki\",\"priority\":260,\"enabled\":true,\"strict_mode\":false,\"require_validation\":false,\"require_approved\":false,\"require_not_expired\":false}")"
  python3 - <<'PY' "$rule_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"rule_id={obj['id']} rule_key={obj['rule_key']}")
PY

  rollout_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/rollouts" "{\"bundle_id\":\"$bundle_id\",\"rollout_key\":\"governance-rollout\",\"target_agent_slug\":\"metrics\",\"target_source_type\":\"wiki\",\"task_pattern\":\"*policy-governance*\",\"priority\":260,\"enabled\":true,\"rollout_mode\":\"full\"}")"
  rollout_id="$(python3 - <<'PY' "$rollout_resp"
import json, sys
print(json.loads(sys.argv[1])['id'])
PY
)"
  echo "rollout_id=$rollout_id"

  resolve_resp="$(curl_json POST "$BASE_URL/v1/knowledge/resolve" "{\"task\":\"policy-governance incident triage\",\"agent_slug\":\"metrics\",\"source_type\":\"wiki\",\"risk_level\":\"high\",\"tags\":[\"policy-governance\"],\"limit\":5,\"retrieval_mode\":\"lexical\",\"ranking_profile\":\"$profile_key\"}")"
  python3 - <<'PY' "$resolve_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"resolve_total={obj['total']}")
if int(obj.get('total', 0)) < 1:
    raise SystemExit('governance resolve returned no items')
PY

  observability_resp="$(curl_json GET "$BASE_URL/v1/knowledge/validation-policy/observability/summary?days=7")"
  python3 - <<'PY' "$observability_resp" "$bundle_key" "$profile_key"
import json, sys
obj = json.loads(sys.argv[1])
bundle_key = sys.argv[2]
profile_key = sys.argv[3]
bundle_keys = [item['key'] for item in obj.get('bundles', [])]
profile_keys = [item['key'] for item in obj.get('ranking_profiles', [])]
print(f"observed_bundles={bundle_keys}")
print(f"observed_profiles={profile_keys}")
if bundle_key not in bundle_keys:
    raise SystemExit('observability summary missing governance bundle')
if profile_key not in profile_keys:
    raise SystemExit('observability summary missing custom ranking profile')
PY

  change_resp="$(curl_json GET "$BASE_URL/v1/knowledge/validation-policy/change-events?limit=20")"
  python3 - <<'PY' "$change_resp" "$bundle_key" "$profile_key"
import json, sys
arr = json.loads(sys.argv[1])
bundle_key = sys.argv[2]
profile_key = sys.argv[3]
entity_keys = [item['entity_key'] for item in arr]
print(f"change_event_keys={entity_keys[:10]}")
if bundle_key not in entity_keys:
    raise SystemExit('change events missing governance bundle')
if profile_key not in entity_keys:
    raise SystemExit('change events missing ranking profile')
PY

  rollback_rollout_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/rollouts/$rollout_id/rollback" '{"actor":"qa-governance"}')"
  python3 - <<'PY' "$rollback_rollout_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"rollback_rollout_entity={obj['entity_key']} action={obj['rollback_action']}")
if obj.get('entity_type') != 'rollout':
    raise SystemExit('rollout rollback returned wrong entity_type')
if obj.get('current_state', {}).get('enabled', True) is not False:
    raise SystemExit('rollout rollback did not disable rollout')
PY

  rollout_list_resp="$(curl_json GET "$BASE_URL/v1/knowledge/validation-policy/rollouts?bundle_id=$bundle_id")"
  python3 - <<'PY' "$rollout_list_resp"
import json, sys
arr = json.loads(sys.argv[1])
enabled = arr[0]['enabled'] if arr else None
print(f"rollout_enabled_after_rollback={enabled}")
if enabled is not False:
    raise SystemExit('rollout remained enabled after rollback')
PY

  rollback_bundle_resp="$(curl_json POST "$BASE_URL/v1/knowledge/validation-policy/bundles/$bundle_id/rollback" '{"actor":"qa-governance"}')"
  python3 - <<'PY' "$rollback_bundle_resp"
import json, sys
obj = json.loads(sys.argv[1])
print(f"rollback_bundle_entity={obj['entity_key']} action={obj['rollback_action']}")
if obj.get('entity_type') != 'bundle':
    raise SystemExit('bundle rollback returned wrong entity_type')
if obj.get('current_state', {}).get('enabled', True) is not False:
    raise SystemExit('bundle rollback did not disable bundle')
PY

  bundle_list_resp="$(curl_json GET "$BASE_URL/v1/knowledge/validation-policy/bundles")"
  python3 - <<'PY' "$bundle_list_resp" "$bundle_key"
import json, sys
arr = json.loads(sys.argv[1])
bundle_key = sys.argv[2]
entry = next((item for item in arr if item.get('bundle_key') == bundle_key), None)
print(f"bundle_enabled_after_rollback={entry.get('enabled') if entry else None}")
if not entry or entry.get('enabled') is not False:
    raise SystemExit('bundle remained enabled after rollback')
PY

  echo "POLICY_GOVERNANCE_FLOW_OK=true"
}

main "$@"