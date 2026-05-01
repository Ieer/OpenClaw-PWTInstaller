#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

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

AGENTS=("$@")
if [[ "${#AGENTS[@]}" -eq 0 ]]; then
  AGENTS=("${DEFAULT_AGENTS[@]}")
fi

PASSED=0
FAILED=0

print_ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

print_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
}

check_agent() {
  local agent="$1"
  local container="openclaw-${agent}"

  if ! docker inspect "$container" >/dev/null 2>&1; then
    print_fail "${container}: container not found"
    FAILED=$((FAILED + 1))
    return
  fi

  local output
  if ! output="$(docker exec "$container" sh -lc '
set -eu
python3 --version
python3 -m pip --version
python3 - <<"PY"
import yaml
print("PyYAML", getattr(yaml, "__version__", "unknown"))
PY
' 2>&1)"; then
    print_fail "${container}: Python runtime incomplete"
    printf '%s\n' "$output" | sed 's/^/  /'
    FAILED=$((FAILED + 1))
    return
  fi

  print_ok "${container}: $(printf '%s' "$output" | tr '\n' '; ' | sed 's/[; ]*$//')"
  PASSED=$((PASSED + 1))
}

echo -e "${CYAN}=== Panopticon Agent Python Runtime 巡检 ===${NC}"
echo "Agents: ${AGENTS[*]}"
echo

for agent in "${AGENTS[@]}"; do
  case "$agent" in
    nox|metrics|email|growth|trades|health|writing|personal)
      check_agent "$agent"
      ;;
    *)
      print_warn "跳过未知 agent: ${agent}"
      ;;
  esac
done

echo
echo -e "${CYAN}=== Summary ===${NC}"
echo "Passed: ${PASSED}"
echo "Failed: ${FAILED}"

if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}结果: 全部 agent 已具备 python3/pip/PyYAML${NC}"
  exit 0
fi

echo -e "${RED}结果: 存在 agent Python 运行态缺口${NC}"
exit 1