#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"
UI_URL="${UI_URL:-http://127.0.0.1:18920/}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:18910/health}"
MAX_RETRIES="${MAX_RETRIES:-10}"
RETRY_INTERVAL_SECONDS="${RETRY_INTERVAL_SECONDS:-2}"

if ! command -v docker >/dev/null 2>&1; then
  echo -e "${RED}[FAIL]${NC} docker not found"
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo -e "${RED}[FAIL]${NC} compose file not found: $COMPOSE_FILE"
  exit 1
fi

echo -e "${CYAN}=== Recover Mission Control Gateway ===${NC}"
echo "Compose: $COMPOSE_FILE"
echo

echo -e "${CYAN}[1/3]${NC} Rebuild/restart mission-control-api and mission-control-ui"
docker compose -f "$COMPOSE_FILE" up -d --build mission-control-api mission-control-ui

echo -e "${CYAN}[2/3]${NC} Force-recreate mission-control-gateway to refresh upstream IPs"
docker compose -f "$COMPOSE_FILE" up -d --force-recreate mission-control-gateway

echo -e "${CYAN}[3/3]${NC} Verify Mission Control entrypoints"
ui_code=""
api_body=""

for attempt in $(seq 1 "$MAX_RETRIES"); do
  ui_code="$(curl -sS -o /dev/null -w '%{http_code}' -L --max-time 10 "$UI_URL" || true)"
  api_body="$(curl -fsS --max-time 10 "$API_HEALTH_URL" || true)"

  if [[ "$ui_code" == "200" && "$api_body" == *'"ok":true'* ]]; then
    break
  fi

  if [[ "$attempt" -lt "$MAX_RETRIES" ]]; then
    sleep "$RETRY_INTERVAL_SECONDS"
  fi
done

if [[ "$ui_code" != "200" ]]; then
  echo -e "${RED}[FAIL]${NC} UI check failed: ${UI_URL} -> HTTP ${ui_code:-ERR}"
  exit 1
fi

if [[ "$api_body" != *'"ok":true'* ]]; then
  echo -e "${RED}[FAIL]${NC} API health check failed: ${API_HEALTH_URL} -> ${api_body:-ERR}"
  exit 1
fi

echo -e "${GREEN}[OK]${NC} Mission Control UI recovered: ${UI_URL} -> HTTP 200"
echo -e "${GREEN}[OK]${NC} Mission Control API healthy: ${API_HEALTH_URL} -> ${api_body}"