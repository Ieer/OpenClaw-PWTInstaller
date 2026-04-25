#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PANOPTICON_HEALTH_SCRIPT="$REPO_ROOT/panopticon/tools/check_panopticon_services.sh"

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

echo -e "${CYAN}=== 系统服务状态检查 ===${NC}"
check_unit "panopticon-mission-control.service"
check_unit "openclaw-cnim.service"

echo
echo -e "${CYAN}=== Panopticon layered health ===${NC}"
if [[ -f "$PANOPTICON_HEALTH_SCRIPT" ]]; then
  if bash "$PANOPTICON_HEALTH_SCRIPT"; then
    :
  else
    FAILED=1
  fi
else
  print_fail "未找到 Panopticon 健康检查脚本: $PANOPTICON_HEALTH_SCRIPT"
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}全部检查通过${NC}"
  exit 0
else
  echo -e "${RED}存在失败项，请按提示排查${NC}"
  exit 1
fi
