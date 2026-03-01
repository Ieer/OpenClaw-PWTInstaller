#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"
VOICE_E2E_SCRIPT="$PANOPTICON_DIR/tools/test_voice_bridge_e2e.sh"
VOICE_CONTAINER="${MC_VOICE_BRIDGE_CONTAINER:-mission-control-voice-bridge}"
CHECK_VOICE_E2E="${CHECK_VOICE_E2E:-auto}"

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
TOTAL_COUNT=${#SERVICES[@]}

echo -e "${CYAN}=== Panopticon ${TOTAL_COUNT} 服务巡检 ===${NC}"
for svc in "${SERVICES[@]}"; do
  if [[ -n "${RUNNING[$svc]:-}" ]]; then
    echo -e "${GREEN}[GREEN]${NC} $svc running"
    OK_COUNT=$((OK_COUNT + 1))
  else
    echo -e "${RED}[RED]${NC} $svc not running"
    FAILED=1
  fi
done

VOICE_FAILED=0
VOICE_CHECK_RAN=0
if [[ "$CHECK_VOICE_E2E" != "0" ]]; then
  if [[ -n "${RUNNING[$VOICE_CONTAINER]:-}" ]]; then
    VOICE_CHECK_RAN=1
    if [[ -x "$VOICE_E2E_SCRIPT" ]]; then
      echo -e "${CYAN}=== Voice Bridge E2E 巡检 ===${NC}"
      if bash "$VOICE_E2E_SCRIPT"; then
        echo -e "${GREEN}[GREEN]${NC} voice-bridge e2e pass"
      else
        echo -e "${RED}[RED]${NC} voice-bridge e2e failed"
        FAILED=1
        VOICE_FAILED=1
      fi
    else
      echo -e "${RED}[RED]${NC} voice e2e 脚本不存在或不可执行: $VOICE_E2E_SCRIPT"
      FAILED=1
      VOICE_FAILED=1
    fi
  else
    if [[ "$CHECK_VOICE_E2E" == "1" ]]; then
      echo -e "${RED}[RED]${NC} voice e2e 强制开启，但容器未运行: $VOICE_CONTAINER"
      FAILED=1
      VOICE_FAILED=1
    else
      echo -e "${CYAN}[SKIP]${NC} voice e2e (容器未运行: $VOICE_CONTAINER, CHECK_VOICE_E2E=auto)"
    fi
  fi
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
  if [[ "$VOICE_CHECK_RAN" -eq 1 ]]; then
    echo -e "${GREEN}结果: ${OK_COUNT}/${TOTAL_COUNT} 服务均为 running，voice e2e 通过${NC}"
  else
    echo -e "${GREEN}结果: ${OK_COUNT}/${TOTAL_COUNT} 服务均为 running${NC}"
  fi
  exit 0
fi

if [[ "$VOICE_FAILED" -eq 1 ]]; then
  echo -e "${RED}结果: ${OK_COUNT}/${TOTAL_COUNT} 服务 running，voice e2e 失败，请执行以下命令排查:${NC}"
else
  echo -e "${RED}结果: ${OK_COUNT}/${TOTAL_COUNT} 服务 running，请执行以下命令排查:${NC}"
fi
echo "docker compose -f $COMPOSE_FILE ps"
if [[ "$VOICE_FAILED" -eq 1 ]]; then
  echo "docker compose -f $COMPOSE_FILE logs --tail=80 $VOICE_CONTAINER"
fi
exit 1
