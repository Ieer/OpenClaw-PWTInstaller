#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PANOPTICON_ROOT}/.." && pwd)"
COMPOSE_FILE="${PANOPTICON_ROOT}/docker-compose.panopticon.yml"
PORT="${MISSION_CONTROL_GATEWAY_PORT:-18920}"
LAN_IP="${MISSION_CONTROL_LAN_IP:-}"
HTTP_TIMEOUT="${HTTP_TIMEOUT:-5}"
HTTP_RETRIES="${HTTP_RETRIES:-3}"
HTTP_RETRY_DELAY="${HTTP_RETRY_DELAY:-2}"
AGENTS="${MISSION_CONTROL_AGENTS:-nox metrics email growth trades health writing personal}"

print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

if [[ -z "${LAN_IP}" ]]; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi

echo -e "${CYAN}=== Mission Control LAN 巡检 ===${NC}"
echo "Repo: ${REPO_ROOT}"
echo "LAN IP: ${LAN_IP:-unknown}"
echo "Gateway port: ${PORT}"
echo

failures=0

if [[ -z "${LAN_IP}" ]]; then
  print_fail "未能自动检测 LAN IP；可用 MISSION_CONTROL_LAN_IP=... 指定。"
  failures=$((failures + 1))
fi

if command -v docker >/dev/null 2>&1; then
  docker compose -f "${COMPOSE_FILE}" ps mission-control-gateway mission-control-ui mission-control-api || true
else
  print_warn "docker 命令不可用，跳过容器状态检查。"
fi
echo

if command -v ss >/dev/null 2>&1; then
  if ss -ltn | grep -Eq "(^|[[:space:]])(0\.0\.0\.0|\[::\]|\*)?:${PORT}[[:space:]]"; then
    print_ok "宿主正在监听 0.0.0.0/[::]:${PORT}"
  elif ss -ltn | grep -Eq ":${PORT}[[:space:]]"; then
    print_warn "端口 ${PORT} 正在监听，但可能不是所有网卡；请检查 docker ports 绑定。"
  else
    print_fail "宿主未监听 ${PORT}。"
    failures=$((failures + 1))
  fi
else
  print_warn "ss 命令不可用，跳过端口监听检查。"
fi

check_url() {
  local label="$1"
  local url="$2"
  local origin="${3:-}"
  local out code time_total attempt
  for ((attempt = 1; attempt <= HTTP_RETRIES; attempt++)); do
    if [[ -n "${origin}" ]]; then
      out="$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time "${HTTP_TIMEOUT}" -H "Origin: ${origin}" "${url}" 2>/dev/null || true)"
    else
      out="$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time "${HTTP_TIMEOUT}" "${url}" 2>/dev/null || true)"
    fi
    code="$(awk '{print $1}' <<< "${out}")"
    time_total="$(awk '{print $2}' <<< "${out}")"
    if [[ "${code}" =~ ^2[0-9][0-9]$|^3[0-9][0-9]$ ]]; then
      if [[ "${attempt}" -gt 1 ]]; then
        print_ok "${label}: ${url} HTTP ${code} (${time_total}s, retry ${attempt}/${HTTP_RETRIES})"
      else
        print_ok "${label}: ${url} HTTP ${code} (${time_total}s)"
      fi
      return
    fi
    if [[ "${attempt}" -lt "${HTTP_RETRIES}" ]]; then
      sleep "${HTTP_RETRY_DELAY}"
    fi
  done
  print_fail "${label}: ${url} HTTP ${code:-ERR}"
  failures=$((failures + 1))
}

check_ws_upgrade() {
  local label="$1"
  local url="$2"
  local origin="$3"
  local code attempt
  for ((attempt = 1; attempt <= HTTP_RETRIES; attempt++)); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --http1.1 --max-time "${HTTP_TIMEOUT}" \
      -H 'Connection: Upgrade' \
      -H 'Upgrade: websocket' \
      -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
      -H 'Sec-WebSocket-Version: 13' \
      -H "Origin: ${origin}" \
      "${url}" 2>/dev/null || true)"
    if [[ "${code}" == "101" ]]; then
      if [[ "${attempt}" -gt 1 ]]; then
        print_ok "${label}: ${url} WebSocket 101 (retry ${attempt}/${HTTP_RETRIES})"
      else
        print_ok "${label}: ${url} WebSocket 101"
      fi
      return
    fi
    if [[ "${attempt}" -lt "${HTTP_RETRIES}" ]]; then
      sleep "${HTTP_RETRY_DELAY}"
    fi
  done
  print_fail "${label}: ${url} WebSocket HTTP ${code:-ERR}"
  failures=$((failures + 1))
}

check_url "本机 loopback gateway" "http://127.0.0.1:${PORT}/"
if [[ -n "${LAN_IP}" ]]; then
  check_url "本机经 LAN IP gateway" "http://${LAN_IP}:${PORT}/"
  LAN_ORIGIN="http://${LAN_IP}:${PORT}"
  for agent in ${AGENTS}; do
    check_url "本机经 LAN IP chat/${agent}" "http://${LAN_IP}:${PORT}/chat/${agent}/" "${LAN_ORIGIN}"
    check_url "本机经 LAN IP chat/${agent} control-ui-config" "http://${LAN_IP}:${PORT}/chat/${agent}/__openclaw/control-ui-config.json" "${LAN_ORIGIN}"
    check_ws_upgrade "本机经 LAN IP chat/${agent}" "http://${LAN_IP}:${PORT}/chat/${agent}/" "${LAN_ORIGIN}"
  done
fi

echo
if python3 - "${PANOPTICON_ROOT}" "${PORT}" "${LAN_IP}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
port = sys.argv[2]
lan_ip = sys.argv[3]
expected = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
if lan_ip:
    expected.add(f"http://{lan_ip}:{port}")

missing_total = 0
print("-- OpenClaw gateway/controlUi --")
for path in sorted((root / "agent-homes").glob("*/openclaw.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    gateway = data.get("gateway", {})
    control_ui = gateway.get("controlUi", {})
    origins = control_ui.get("allowedOrigins", [])
    origins = [str(item) for item in origins if str(item).strip()]
    missing = sorted(expected - set(origins))
    problems = []
    if gateway.get("bind") != "lan":
        problems.append(f"gateway.bind={gateway.get('bind')!r}")
    if control_ui.get("allowInsecureAuth") is not True:
        problems.append("allowInsecureAuth is not true")
    if control_ui.get("dangerouslyDisableDeviceAuth") is not True:
        problems.append("dangerouslyDisableDeviceAuth is not true")
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if problems:
        missing_total += 1
        print(f"[MISS] {path.parent.name}: {'; '.join(problems)}")
    else:
        print(f"[OK] {path.parent.name}: bind=lan, controlUi auth disabled, {len(origins)} origins")

if missing_total:
    print(f"Missing origin files: {missing_total}")
    sys.exit(2)
PY
then
  origin_status=0
else
  origin_status=$?
fi
if [[ "${origin_status}" -ne 0 ]]; then
  print_warn "存在 Origin 白名单缺口；可运行: python panopticon/tools/sync_mission_control_lan_origins.py"
  failures=$((failures + 1))
fi

echo
if [[ -n "${LAN_IP}" ]]; then
  echo "推荐入口: http://${LAN_IP}:${PORT}/"
  echo "Agent Chat: http://${LAN_IP}:${PORT}/chat/<agent>/"
fi

if [[ "${failures}" -eq 0 ]]; then
  print_ok "本机侧 LAN 入口配置通过。若远端仍不可访问，优先检查客户端是否在同一网段、路由器 AP isolation/访客网络、以及是否使用了上面的精确入口。"
  exit 0
fi

print_fail "发现 ${failures} 个问题。"
exit 1
