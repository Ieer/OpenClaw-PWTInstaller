#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

HOST="${HOST:-127.0.0.1}"
HTTP_TIMEOUT="${HTTP_TIMEOUT:-5}"
TCP_TIMEOUT="${TCP_TIMEOUT:-3}"

AGENTS=(
  nox
  metrics
  email
  growth
  trades
  health
  writing
  personal
)

GATEWAY_PORTS=(18801 18811 18821 18831 18841 18851 18861 18871)
BRIDGE_PORTS=(18802 18812 18822 18832 18842 18852 18862 18872)

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

check_gateway_http() {
  local agent="$1"
  local port="$2"
  local url="http://${HOST}:${port}"

  TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

  local out code time_total
  out="$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time "$HTTP_TIMEOUT" "$url" 2>/dev/null || true)"
  code="$(awk '{print $1}' <<< "$out")"
  time_total="$(awk '{print $2}' <<< "$out")"

  if [[ "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    if [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
      print_ok "${agent} Gateway ${url} reachable (HTTP ${code}, ${time_total}s)"
    else
      print_warn "${agent} Gateway ${url} reachable but non-2xx (HTTP ${code}, ${time_total}s)"
    fi
  else
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    print_fail "${agent} Gateway ${url} unreachable (HTTP ${code:-ERR})"
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
echo "Host: ${HOST} | HTTP timeout: ${HTTP_TIMEOUT}s | TCP timeout: ${TCP_TIMEOUT}s"
echo

echo -e "${CYAN}-- Gateway (HTTP) --${NC}"
for i in "${!AGENTS[@]}"; do
  check_gateway_http "${AGENTS[$i]}" "${GATEWAY_PORTS[$i]}"
done

echo
echo -e "${CYAN}-- Bridge (TCP) --${NC}"
for i in "${!AGENTS[@]}"; do
  check_bridge_tcp "${AGENTS[$i]}" "${BRIDGE_PORTS[$i]}"
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
