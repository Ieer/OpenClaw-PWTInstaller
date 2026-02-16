#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"

SERVICES=(
  mc-redis
  mc-postgres
  mission-control-api
  mission-control-ui
  mc-heartbeat
  openclaw-nox
  openclaw-metrics
  openclaw-email
  openclaw-growth
  openclaw-trades
  openclaw-health
  openclaw-writing
  openclaw-personal
)

if ! command -v docker >/dev/null 2>&1; then
  echo -e "${RED}[FAIL]${NC} docker 未安装或不在 PATH"
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo -e "${RED}[FAIL]${NC} 未找到 compose 文件: $COMPOSE_FILE"
  exit 1
fi

declare -A RUNNING=()
while IFS= read -r svc; do
  [[ -n "$svc" ]] && RUNNING["$svc"]=1
done < <(docker compose -f "$COMPOSE_FILE" ps --services --filter status=running 2>/dev/null || true)

FAILED=0
OK_COUNT=0

echo -e "${CYAN}=== Panopticon 13 服务巡检 ===${NC}"
for svc in "${SERVICES[@]}"; do
  if [[ -n "${RUNNING[$svc]:-}" ]]; then
    echo -e "${GREEN}[GREEN]${NC} $svc running"
    OK_COUNT=$((OK_COUNT + 1))
  else
    echo -e "${RED}[RED]${NC} $svc not running"
    FAILED=1
  fi
done

echo
if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}结果: ${OK_COUNT}/13 服务均为 running${NC}"
  exit 0
fi

echo -e "${RED}结果: ${OK_COUNT}/13 服务 running，请执行以下命令排查:${NC}"
echo "docker compose -f $COMPOSE_FILE ps"
exit 1
