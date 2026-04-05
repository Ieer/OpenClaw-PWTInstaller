#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/panopticon/docker-compose.panopticon.yml"
API_SERVICE="${API_SERVICE:-mission-control-api}"
TARGET_AGENT="${TARGET_AGENT:-nox}"
DISALLOWED_AGENT="${DISALLOWED_AGENT:-shadow}"

print_ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

print_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
}

cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  print_fail "docker not found"
  exit 1
fi

if ! docker compose -f "$COMPOSE_FILE" ps "$API_SERVICE" >/dev/null 2>&1; then
  print_fail "service ${API_SERVICE} is not available in compose"
  exit 1
fi

echo -e "${CYAN}=== Agent Controller Auth Regression ===${NC}"
echo "Compose: ${COMPOSE_FILE}"
echo "Probe service: ${API_SERVICE}"
echo

output="$({ docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python - "$TARGET_AGENT" "$DISALLOWED_AGENT" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

target_agent = sys.argv[1]
disallowed_agent = sys.argv[2]
base_url = (os.getenv("MC_AGENT_CONTROLLER_URL") or "").strip().rstrip("/")
token = (os.getenv("MC_AGENT_CONTROLLER_AUTH_TOKEN") or "").strip()

if not base_url:
    print(json.dumps({"ok": False, "error": "MC_AGENT_CONTROLLER_URL missing in runtime env"}, ensure_ascii=False))
    raise SystemExit(2)

if not token:
    print(json.dumps({"ok": False, "error": "MC_AGENT_CONTROLLER_AUTH_TOKEN missing in runtime env"}, ensure_ascii=False))
    raise SystemExit(2)


def request_status(agent: str, action: str, auth_header: str | None):
    url = f"{base_url}/v1/containers/{agent}/control"
    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    request = urllib.request.Request(
        url=url,
        method="POST",
        headers=headers,
        data=json.dumps({"action": action}).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=8.0) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"status": int(response.status), "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"status": int(exc.code), "body": body}


results = {
    "missing_token": request_status(target_agent, "restart", None),
    "wrong_token": request_status(target_agent, "restart", "Bearer definitely-wrong-token"),
    "invalid_action_with_valid_token": request_status(target_agent, "__invalid_action__", f"Bearer {token}"),
    "disallowed_agent_with_valid_token": request_status(disallowed_agent, "restart", f"Bearer {token}"),
}

expectations = {
    "missing_token": 401,
    "wrong_token": 403,
    "invalid_action_with_valid_token": 400,
    "disallowed_agent_with_valid_token": 403,
}

failures = []
for key, expected in expectations.items():
    actual = int(results[key]["status"])
    if actual != expected:
        failures.append({"case": key, "expected": expected, "actual": actual, "body": results[key]["body"][:300]})

print(json.dumps({"ok": not failures, "base_url": base_url, "results": results, "failures": failures}, ensure_ascii=False))
raise SystemExit(0 if not failures else 1)
PY
} 2>&1)"

status=$?
echo "$output"

if [[ $status -ne 0 ]]; then
  print_fail "agent-controller auth regression failed"
  exit $status
fi

print_ok "agent-controller rejects missing/wrong token and only reaches business validation with the correct token"