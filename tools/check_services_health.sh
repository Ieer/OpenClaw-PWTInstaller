#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

FAILED=0

print_ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

print_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  FAILED=1
}

check_unit() {
  local unit="$1"
  local enabled active

  enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
  active="$(systemctl is-active "$unit" 2>/dev/null || true)"

  if [[ "$enabled" == "enabled" ]]; then
    print_ok "$unit enabled"
  else
    print_fail "$unit enabled state: ${enabled:-unknown}"
  fi

  if [[ "$active" == "active" ]]; then
    print_ok "$unit active"
  else
    print_fail "$unit active state: ${active:-unknown}"
  fi
}

check_port() {
  local port="$1"
  local label="$2"

  if ss -ltn "( sport = :$port )" 2>/dev/null | awk 'NR>1 {found=1} END {exit(found?0:1)}'; then
    print_ok "$label 端口 $port 正在监听"
  else
    print_fail "$label 端口 $port 未监听"
  fi
}

check_http() {
  local url="$1"
  local label="$2"

  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" || true)"
  if [[ "$code" == "200" ]]; then
    print_ok "$label 可访问 ($url)"
  else
    print_fail "$label 异常 ($url, HTTP ${code:-ERR})"
  fi
}

echo -e "${CYAN}=== 系统服务状态检查 ===${NC}"
check_unit "panopticon-mission-control.service"
check_unit "openclaw-cnim.service"

echo
echo -e "${CYAN}=== 端口健康检查 ===${NC}"
check_port "18910" "Mission Control API"
check_port "18920" "Mission Control UI"
check_port "27216" "OpenClaw Gateway"
check_port "27217" "OpenClaw Bridge"

echo
echo -e "${CYAN}=== HTTP健康检查 ===${NC}"
check_http "http://127.0.0.1:18910/health" "Mission Control API /health"
check_http "http://127.0.0.1:18920" "Mission Control UI"

echo
if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}全部检查通过${NC}"
  exit 0
else
  echo -e "${RED}存在失败项，请按提示排查${NC}"
  exit 1
fi
