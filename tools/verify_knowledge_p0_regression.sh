#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18910}"
COMPOSE_FILE="${COMPOSE_FILE:-panopticon/docker-compose.panopticon.yml}"
MAX_RETRIES="${MAX_RETRIES:-3}"

run_with_retry() {
  local name="$1"
  shift
  local attempt=1
  until "$@"; do
    if [[ "$attempt" -ge "$MAX_RETRIES" ]]; then
      echo "[FAIL] ${name} failed after ${attempt} attempts" >&2
      return 1
    fi
    attempt=$((attempt + 1))
    echo "[WARN] ${name} failed, retrying (${attempt}/${MAX_RETRIES})..." >&2
    sleep 2
  done
  echo "[OK] ${name}" >&2
}

check_health() {
  local resp
  resp="$(curl -f -sS "$BASE_URL/health")"
  python3 - <<'PY' "$resp"
import json, sys
obj = json.loads(sys.argv[1])
if not obj.get("ok"):
    raise SystemExit("health is not ok")
print("health_ok=true")
PY
}

check_migration_head() {
  local out
  out="$(docker compose -f "$COMPOSE_FILE" run --rm mission-control-api alembic current)"
  echo "$out"
  if ! grep -q "head" <<<"$out"; then
    echo "[FAIL] alembic current is not at head" >&2
    return 1
  fi
}

check_resolve_metrics() {
  local resp
  resp="$(curl -f -sS "$BASE_URL/v1/knowledge/resolve/metrics?days=7&top_reasons=5")"
  python3 - <<'PY' "$resp"
import json, sys
obj = json.loads(sys.argv[1])
required = [
    "total_resolve_requests",
    "requests_without_hits",
    "requests_without_rejections",
    "total_selected_units",
    "total_rejected_units",
    "resolve_hit_rate",
    "resolve_error_rate",
    "resolve_rejection_rate",
    "unit_selection_rate",
    "expired_rejection_rate",
    "risk_breakdown",
]
missing = [k for k in required if k not in obj]
if missing:
    raise SystemExit(f"metrics missing keys: {missing}")
for item in obj.get("top_reject_reasons", []):
    if "rate" not in item:
        raise SystemExit("top_reject_reasons missing rate")
print("metrics_total_requests=", obj.get("total_resolve_requests"))
print("metrics_hit_rate=", obj.get("resolve_hit_rate"))
print("metrics_error_rate=", obj.get("resolve_error_rate"))
print("metrics_rejection_rate=", obj.get("resolve_rejection_rate"))
print("metrics_expired_rejection_rate=", obj.get("expired_rejection_rate"))
PY
}

main() {
  run_with_retry "health" check_health
  run_with_retry "alembic current head" check_migration_head
  run_with_retry "minimal flow" bash tools/verify_knowledge_minimal_flow.sh
  run_with_retry "policy audit flow" bash tools/verify_knowledge_policy_audit_flow.sh
  run_with_retry "multiformat chunk flow" bash tools/verify_knowledge_multiformat_chunk_flow.sh
  run_with_retry "ocr flow" bash tools/verify_knowledge_ocr_flow.sh
  run_with_retry "resolve metrics" check_resolve_metrics
  echo "P0_REGRESSION_OK=true"
}

main "$@"
