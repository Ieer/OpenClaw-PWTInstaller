#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

HOST="${HOST:-127.0.0.1}"
HTTP_HOST="${HTTP_HOST:-localhost}"
HTTP_TIMEOUT="${HTTP_TIMEOUT:-5}"
TCP_TIMEOUT="${TCP_TIMEOUT:-3}"
GATEWAY_HTTP_STRICT="${GATEWAY_HTTP_STRICT:-0}"

DEFAULT_AGENTS=(
  nox
  metrics
  email
  growth
  trades
  health
  writing
  personal
)

declare -A GATEWAY_PORTS=(
  [nox]=18801
  [metrics]=18811
  [email]=18821
  [growth]=18831
  [trades]=18841
  [health]=18851
  [writing]=18861
  [personal]=18871
)

declare -A BRIDGE_PORTS=(
  [nox]=18802
  [metrics]=18812
  [email]=18822
  [growth]=18832
  [trades]=18842
  [health]=18852
  [writing]=18862
  [personal]=18872
)

AGENTS=("$@")
if [[ "${#AGENTS[@]}" -eq 0 ]]; then
  AGENTS=("${DEFAULT_AGENTS[@]}")
fi

TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

print_ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

print_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
}

validate_agent() {
  local agent="$1"

  if [[ -n "${GATEWAY_PORTS[$agent]+x}" && -n "${BRIDGE_PORTS[$agent]+x}" ]]; then
    return 0
  fi

  print_fail "未知 agent: ${agent}"
  exit 1
}

check_gateway() {
  local agent="$1"
  local port="$2"
  local url="http://${HTTP_HOST}:${port}"

  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if timeout "$TCP_TIMEOUT" bash -lc "</dev/tcp/${HOST}/${port}" >/dev/null 2>&1; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    print_ok "${agent} Gateway tcp://${HOST}:${port} open"
  else
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    print_fail "${agent} Gateway tcp://${HOST}:${port} closed/unreachable"
    return
  fi

  local out code time_total
  out="$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time "$HTTP_TIMEOUT" "$url" 2>/dev/null || true)"
  code="$(awk '{print $1}' <<< "$out")"
  time_total="$(awk '{print $2}' <<< "$out")"

  if [[ "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
    if [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
      print_ok "${agent} Gateway HTTP probe ${url} ok (HTTP ${code}, ${time_total}s)"
    else
      print_warn "${agent} Gateway HTTP probe ${url} non-2xx (HTTP ${code}, ${time_total}s)"
    fi
  elif [[ "$GATEWAY_HTTP_STRICT" == "1" ]]; then
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    print_fail "${agent} Gateway HTTP probe ${url} failed (HTTP ${code:-ERR})"
  else
    print_warn "${agent} Gateway HTTP probe ${url} skipped/failed (HTTP ${code:-ERR}); TCP already reachable"
  fi
}

check_bridge_tcp() {
  local agent="$1"
  local port="$2"

  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  if timeout "$TCP_TIMEOUT" bash -lc "</dev/tcp/${HOST}/${port}" >/dev/null 2>&1; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    print_ok "${agent} Bridge tcp://${HOST}:${port} open"
  else
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    print_fail "${agent} Bridge tcp://${HOST}:${port} closed/unreachable"
  fi
}

echo -e "${CYAN}=== Panopticon Agent Endpoint 巡检 ===${NC}"
echo "TCP host: ${HOST} | HTTP host: ${HTTP_HOST} | HTTP timeout: ${HTTP_TIMEOUT}s | TCP timeout: ${TCP_TIMEOUT}s"
echo

for agent in "${AGENTS[@]}"; do
  validate_agent "$agent"
done

echo -e "${CYAN}-- Gateway (TCP + optional HTTP probe) --${NC}"
for agent in "${AGENTS[@]}"; do
  check_gateway "$agent" "${GATEWAY_PORTS[$agent]}"
done

echo
echo -e "${CYAN}-- Bridge (TCP) --${NC}"
for agent in "${AGENTS[@]}"; do
  check_bridge_tcp "$agent" "${BRIDGE_PORTS[$agent]}"
done

echo
echo -e "${CYAN}=== Summary ===${NC}"
echo "Passed: ${PASSED_CHECKS}/${TOTAL_CHECKS}"
echo "Failed: ${FAILED_CHECKS}/${TOTAL_CHECKS}"

if [[ "$FAILED_CHECKS" -eq 0 ]]; then
  echo -e "${GREEN}结果: 全部可访问${NC}"
  exit 0
fi

echo -e "${RED}结果: 存在不可访问端点${NC}"
exit 1
