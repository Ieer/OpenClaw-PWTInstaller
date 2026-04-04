#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:18910}"
AUTH_TOKEN="${MC_API_TOKEN:-${AUTH_TOKEN:-}}"
ITERATIONS="${ITERATIONS:-20}"
MODE="${MODE:-hybrid}"
QUERY_TASK="${QUERY_TASK:-incident response operations production triage}"
AGENT_SLUG="${AGENT_SLUG:-metrics}"
SOURCE_TYPE="${SOURCE_TYPE:-wiki}"
RISK_LEVEL="${RISK_LEVEL:-high}"
SEMANTIC_QUERY="${SEMANTIC_QUERY:-incident response operations production triage}"
RANKING_PROFILE="${RANKING_PROFILE:-precision}"

curl_json() {
  local method="$1"
  local url="$2"
  local data="${3:-}"
  local -a args
  args=(-sS -X "$method" "$url" -H "Content-Type: application/json")
  if [[ -n "$AUTH_TOKEN" ]]; then
    args+=(-H "Authorization: Bearer $AUTH_TOKEN")
  fi
  if [[ -n "$data" ]]; then
    args+=(-d "$data")
  fi
  curl "${args[@]}"
}

main() {
  local payload
  local results_file=""
  results_file="$(mktemp)"
  trap 'if [[ -n "${results_file:-}" ]]; then rm -f "$results_file"; fi' EXIT

  payload="$(cat <<JSON
{
  "task": "${QUERY_TASK}",
  "agent_slug": "${AGENT_SLUG}",
  "source_type": "${SOURCE_TYPE}",
  "risk_level": "${RISK_LEVEL}",
  "limit": 10,
  "retrieval_mode": "${MODE}",
  "ranking_profile": "${RANKING_PROFILE}",
  "semantic_query": "${SEMANTIC_QUERY}",
  "min_semantic_similarity": 0.2,
  "min_score": 1.0
}
JSON
)"

  for ((i=1; i<=ITERATIONS; i++)); do
    local started ended elapsed
    started="$(python3 - <<'PY'
import time
print(time.perf_counter())
PY
)"
    curl_json POST "$BASE_URL/v1/knowledge/resolve" "$payload" >/dev/null
    ended="$(python3 - <<'PY'
import time
print(time.perf_counter())
PY
)"
    elapsed="$(python3 - <<'PY' "$started" "$ended"
import sys
start = float(sys.argv[1])
end = float(sys.argv[2])
print((end - start) * 1000.0)
PY
)"
    echo "$elapsed" >> "$results_file"
  done

  python3 - <<'PY' "$results_file" "$MODE" "$ITERATIONS"
from pathlib import Path
import statistics
import sys

path = Path(sys.argv[1])
mode = sys.argv[2]
iterations = int(sys.argv[3])
values = [float(line.strip()) for line in path.read_text().splitlines() if line.strip()]
if not values:
    raise SystemExit('no benchmark samples collected')
values_sorted = sorted(values)
def percentile(data, pct):
    if len(data) == 1:
        return data[0]
    index = (len(data) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(data) - 1)
    fraction = index - lower
    return data[lower] + (data[upper] - data[lower]) * fraction

print(f"benchmark_mode={mode}")
print(f"benchmark_iterations={iterations}")
print(f"latency_ms_min={min(values_sorted):.2f}")
print(f"latency_ms_p50={percentile(values_sorted, 0.50):.2f}")
print(f"latency_ms_p95={percentile(values_sorted, 0.95):.2f}")
print(f"latency_ms_max={max(values_sorted):.2f}")
print(f"latency_ms_mean={statistics.mean(values_sorted):.2f}")
PY
}

main "$@"