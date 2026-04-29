#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"
PANOPTICON_DOTENV_FILE="$PANOPTICON_DIR/.env"
PANOPTICON_MANIFEST_FILE="$PANOPTICON_DIR/agents.manifest.yaml"
PANOPTICON_GENERATOR_SCRIPT="$PANOPTICON_DIR/tools/generate_panopticon.py"
VOICE_ASSESS_SCRIPT="$PANOPTICON_DIR/tools/assess_voice_service.py"
MISSION_CONTROL_ENV_FILE="$PANOPTICON_DIR/env/mission-control.env"
MISSION_CONTROL_API_BASE="${MISSION_CONTROL_API_BASE:-http://localhost:18910}"
MISSION_CONTROL_HEALTH_URL="${MISSION_CONTROL_API_BASE%/}/health"
MISSION_CONTROL_READY_URL="${MISSION_CONTROL_API_BASE%/}/ready"
CONTAINER_HEALTH_URL="${MISSION_CONTROL_API_BASE%/}/v1/observability/container-health"
VOICE_CONTAINER="${MC_VOICE_BRIDGE_CONTAINER:-mission-control-voice-bridge}"
CHECK_VOICE_E2E="${CHECK_VOICE_E2E:-auto}"
CHAT_PROXY_EXPECTED="${CHAT_PROXY_EXPECTED:-websocket}"
CHAT_PROXY_URL="${CHAT_PROXY_URL:-http://localhost:18920/chat/nox/}"

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

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}[FAIL]${NC} curl 未安装或不在 PATH"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${RED}[FAIL]${NC} python3 未安装或不在 PATH"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo -e "${RED}[FAIL]${NC} docker compose 不可用"
  exit 1
fi

print_ok() {
  echo -e "${GREEN}[GREEN]${NC} $1"
}

print_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

print_fail() {
  echo -e "${RED}[RED]${NC} $1"
}

print_skip() {
  echo -e "${CYAN}[SKIP]${NC} $1"
}

section_header() {
  echo
  echo -e "${CYAN}=== $1 ===${NC}"
}

load_env_value() {
  local file="$1"
  local key="$2"

  if [[ ! -f "$file" ]]; then
  return 0
  fi

  python3 - "$file" "$key" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]

try:
  lines = path.read_text(encoding='utf-8').splitlines()
except OSError:
  raise SystemExit(0)

for raw_line in lines:
  stripped = raw_line.strip()
  if not stripped or stripped.startswith('#') or '=' not in raw_line:
    continue
  current_key, current_value = raw_line.split('=', 1)
  if current_key.strip() == key:
    print(current_value.strip())
    break
PY
}

MISSION_CONTROL_AUTH_TOKEN="${MC_AUTH_TOKEN:-}"
if [[ -z "$MISSION_CONTROL_AUTH_TOKEN" ]]; then
  MISSION_CONTROL_AUTH_TOKEN="$(load_env_value "$MISSION_CONTROL_ENV_FILE" MC_AUTH_TOKEN)"
fi

mark_failure() {
  local layer="$1"
  FAILED=1
  case "$layer" in
    host)
      HOST_FAILED=1
      ;;
    liveness)
      LIVENESS_FAILED=1
      ;;
    readiness)
      READINESS_FAILED=1
      ;;
  esac
}

resolve_bind_path() {
  local raw_value="$1"
  local fallback_relative="$2"

  python3 - "$PANOPTICON_DIR" "$raw_value" "$fallback_relative" <<'PY'
import os
import sys
from pathlib import Path

base = Path(sys.argv[1]).resolve()
raw = sys.argv[2].strip()
fallback = sys.argv[3]

if raw:
  candidate = Path(raw) if os.path.isabs(raw) else (base / raw)
else:
  candidate = base / fallback

print(candidate.resolve())
PY
}

check_directory_state() {
  local path="$1"
  local label="$2"
  local layer="$3"
  local on_missing="$4"

  if [[ -d "$path" ]]; then
    if [[ -w "$path" ]]; then
      print_ok "$label 可写 ($path)"
    else
      print_fail "$label 不可写 ($path)"
      mark_failure "$layer"
    fi
    return 0
  fi

  local parent_dir
  parent_dir="$(dirname "$path")"
  if [[ "$on_missing" == "warn" && -d "$parent_dir" && -w "$parent_dir" ]]; then
    print_warn "$label 不存在，但父目录可写 ($path)"
    return 0
  fi

  print_fail "$label 不存在或父目录不可写 ($path)"
  mark_failure "$layer"
  return 1
}

check_http_status() {
  local url="$1"
  local label="$2"
  local layer="$3"
  local expected="${4:-200}"
  local code

  code="$(curl -L -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)"
  if [[ "$code" == "$expected" ]]; then
    print_ok "$label HTTP $expected ($url)"
    return 0
  fi

  print_fail "$label failed ($url, HTTP ${code:-ERR}, expected $expected)"
  mark_failure "$layer"
  return 1
}

check_websocket_upgrade() {
  local url="$1"
  local label="$2"
  local layer="$3"
  local response code

  response="$(curl -i -sS --max-time 5 \
    -H 'Connection: Upgrade' \
    -H 'Upgrade: websocket' \
    -H 'Sec-WebSocket-Version: 13' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    "$url" 2>/dev/null || true)"
  code="$(awk 'BEGIN { code="" } /^HTTP\// { code=$2 } END { print code }' <<< "$response")"

  if [[ "$code" == "101" ]]; then
    print_ok "$label WebSocket upgrade 101 ($url)"
    return 0
  fi

  print_fail "$label failed ($url, HTTP ${code:-ERR}, expected 101 upgrade)"
  mark_failure "$layer"
  return 1
}

check_chat_proxy_readiness() {
  case "$CHAT_PROXY_EXPECTED" in
    websocket)
      check_websocket_upgrade "$CHAT_PROXY_URL" "Mission Control chat proxy /chat/nox/" readiness
      ;;
    http)
      check_http_status "$CHAT_PROXY_URL" "Mission Control chat proxy /chat/nox/" readiness 200
      ;;
    none|skip)
      print_skip "Mission Control chat proxy readiness 已跳过 (CHAT_PROXY_EXPECTED=$CHAT_PROXY_EXPECTED)"
      ;;
    *)
      print_fail "CHAT_PROXY_EXPECTED 无效: $CHAT_PROXY_EXPECTED (expected websocket|http|none)"
      mark_failure readiness
      return 1
      ;;
  esac
}

refresh_running_services() {
  RUNNING=()
  while IFS= read -r svc; do
    [[ -n "$svc" ]] && RUNNING["$svc"]=1
  done < <(docker compose -f "$COMPOSE_FILE" ps --services --filter status=running 2>/dev/null || true)
}

check_local_env_overrides() {
  if [[ -f "$PANOPTICON_DOTENV_FILE" ]]; then
    print_ok "panopticon/.env 已存在"
  else
    print_warn "panopticon/.env 缺失；Compose 将回退到仓库内默认 bind mount 路径"
  fi

  local example target
  for example in "$PANOPTICON_DIR"/env/*.env.example; do
    [[ -e "$example" ]] || continue
    target="${example%.example}"
    if [[ -f "$target" ]]; then
      print_ok "本地 env 覆盖已存在: $(basename "$target")"
    else
      print_warn "本地 env 覆盖缺失: ${target#$PANOPTICON_DIR/}"
    fi
  done
}

check_runtime_paths() {
  local data_dir_raw usb_host_raw knowledge_raw_raw
  local data_dir usb_host_path knowledge_raw_path

  data_dir_raw="$(load_env_value "$PANOPTICON_DOTENV_FILE" PANOPTICON_DATA_DIR)"
  usb_host_raw="$(load_env_value "$PANOPTICON_DOTENV_FILE" PANOPTICON_USB_HOST_PATH)"
  knowledge_raw_raw="$(load_env_value "$PANOPTICON_DOTENV_FILE" PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH)"

  data_dir="$(resolve_bind_path "$data_dir_raw" ".")"
  usb_host_path="$(resolve_bind_path "$usb_host_raw" "shared-usb")"
  knowledge_raw_path="$(resolve_bind_path "$knowledge_raw_raw" "mission-control/knowledge-sources")"

  check_directory_state "$data_dir" "PANOPTICON_DATA_DIR" host warn || true
  check_directory_state "$usb_host_path" "PANOPTICON_USB_HOST_PATH" host warn || true
  check_directory_state "$knowledge_raw_path" "PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH" host warn || true
}

check_compose_drift() {
  if ! python3 - <<'PY' >/dev/null 2>&1
import yaml
PY
  then
    print_warn "python3 缺少 PyYAML，跳过 compose drift 检查"
    return 0
  fi

  if python3 - "$PANOPTICON_GENERATOR_SCRIPT" "$PANOPTICON_MANIFEST_FILE" "$COMPOSE_FILE" <<'PY'
import importlib.util
import sys
from pathlib import Path

generator_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
compose_path = Path(sys.argv[3])

spec = importlib.util.spec_from_file_location("panopticon_generate_panopticon", generator_path)
if spec is None or spec.loader is None:
  raise SystemExit(1)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

manifest = module.load_manifest(manifest_path)
expected = module.render_compose(manifest)
actual = compose_path.read_text(encoding="utf-8")

if actual != expected:
  raise SystemExit(1)
PY
  then
    print_ok "docker-compose.panopticon.yml 与 manifest 保持同步"
    return 0
  fi

  print_fail "docker-compose.panopticon.yml 与 manifest 漂移；请运行 python3 panopticon/tools/generate_panopticon.py --prune"
  mark_failure host
  return 1
}

check_container_health() {
  local token="$1"
  local auth_state=0
  local tmp_body code

  if [[ -n "$token" ]]; then
  auth_state=1
  fi

  tmp_body="$(mktemp)"
  local -a curl_args=(
  -sS
  -L
  --max-time 10
  -H "Accept: application/json"
  -o "$tmp_body"
  -w '%{http_code}'
  )

  if [[ -n "$token" ]]; then
  curl_args+=(-H "Authorization: Bearer ${token}")
  fi

  code="$(curl "${curl_args[@]}" "$CONTAINER_HEALTH_URL" 2>/dev/null || true)"
  code="${code:-000}"

  if python3 - "$code" "$tmp_body" "$auth_state" "$MISSION_CONTROL_ENV_FILE" <<'PY'
import json
import sys
from pathlib import Path

http_code_raw = sys.argv[1].strip()
body_path = Path(sys.argv[2])
auth_state = sys.argv[3].strip() == '1'
env_file = sys.argv[4]

try:
  http_code = int(http_code_raw or '0')
except ValueError:
  http_code = 0

body = body_path.read_text(encoding='utf-8', errors='replace').strip()

def fail(message: str) -> None:
  print(message)
  raise SystemExit(1)

if http_code in {401, 403}:
  if auth_state:
    fail(f'container-health auth failed (HTTP {http_code}); check MC_AUTH_TOKEN and {env_file}')
  fail(f'container-health requires MC_AUTH_TOKEN (HTTP {http_code}); set MC_AUTH_TOKEN or populate {env_file}')

if http_code != 200:
  if body:
    fail(f'container-health returned HTTP {http_code}: {body[:500]}')
  fail(f'container-health returned HTTP {http_code} with empty body')

try:
  payload = json.loads(body)
except json.JSONDecodeError as exc:
  fail(f'container-health returned non-JSON body: {exc}')

if not isinstance(payload, dict):
  fail(f'container-health returned unexpected payload type: {type(payload).__name__}')

summary_keys = [
  ('compose_ok', 'compose_total', 'compose'),
  ('port_ok', 'port_total', 'port'),
  ('http_ok', 'http_total', 'http'),
  ('overall_ok', 'overall_total', 'overall'),
]

errors = []
for ok_key, total_key, label in summary_keys:
  ok_value = payload.get(ok_key)
  total_value = payload.get(total_key)
  if not isinstance(ok_value, int) or not isinstance(total_value, int):
    errors.append(f'{label} counts missing or invalid')
  elif ok_value < total_value:
    errors.append(f'{label} {ok_value}/{total_value}')

signals = payload.get('signals')
failed_signals = []
if isinstance(signals, list):
  for signal in signals:
    if not isinstance(signal, dict):
      continue
    if signal.get('ok') is not True:
      source = str(signal.get('source') or '?')
      name = str(signal.get('name') or '?')
      target = str(signal.get('target') or '?')
      detail = str(signal.get('detail') or 'no detail')
      failed_signals.append(f'{source}:{name} -> {target} ({detail})')
else:
  errors.append('signals missing or invalid')

if errors or failed_signals:
  if errors:
    print('container-health summary check failed: ' + '; '.join(errors))
  if failed_signals:
    print('failed signals:')
    for item in failed_signals:
      print(f'  - {item}')
  raise SystemExit(1)

compose_ok = payload.get('compose_ok', 0)
compose_total = payload.get('compose_total', 0)
port_ok = payload.get('port_ok', 0)
port_total = payload.get('port_total', 0)
http_ok = payload.get('http_ok', 0)
http_total = payload.get('http_total', 0)
overall_ok = payload.get('overall_ok', 0)
overall_total = payload.get('overall_total', 0)
overall_ratio = payload.get('overall_ratio', 0.0)

try:
  overall_ratio_value = float(overall_ratio)
except (TypeError, ValueError):
  overall_ratio_value = 0.0

print(
  'container-health ok: '
  f'compose {compose_ok}/{compose_total}, '
  f'port {port_ok}/{port_total}, '
  f'http {http_ok}/{http_total}, '
  f'overall {overall_ok}/{overall_total}, '
  f'ratio {overall_ratio_value:.2f}'
)
PY
  then
  print_ok "Mission Control container-health healthy ($CONTAINER_HEALTH_URL)"
  rm -f "$tmp_body"
  return 0
  fi

  print_fail "Mission Control container-health 异常 ($CONTAINER_HEALTH_URL)"
  mark_failure readiness
  rm -f "$tmp_body"
  return 1
}

voice_failure_summary() {
  local report_path="$1"
  local stdout_path="$2"

  python3 - "$report_path" "$stdout_path" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
stdout_path = Path(sys.argv[2])

def fmt_list(values: object) -> str:
    if not isinstance(values, list) or not values:
      return "[]"
    return "[" + ", ".join(str(item) for item in values) + "]"

def load_report() -> dict[str, object] | None:
  if not report_path.exists():
    return None
  try:
    payload = json.loads(report_path.read_text(encoding='utf-8'))
  except Exception:
    return None
  return payload if isinstance(payload, dict) else None

def find_check(report: dict[str, object] | None, name: str) -> dict[str, object] | None:
  if not report:
    return None
  checks = report.get('checks')
  if not isinstance(checks, list):
    return None
  for check in checks:
    if isinstance(check, dict) and str(check.get('name') or '') == name:
      return check
  return None

report = load_report()
bridge_container = find_check(report, 'bridge_container')
bridge_smoke = find_check(report, 'bridge_smoke')
command_closure = find_check(report, 'command_closure')
api_health = find_check(report, 'api_health')

if api_health and str(api_health.get('status') or '') == 'fail':
  http_status = api_health.get('http_status')
  print(f'voice smoke failed: Mission Control /health returned HTTP {http_status}')
  raise SystemExit(0)

if bridge_container and str(bridge_container.get('status') or '') == 'fail':
  reason = str(bridge_container.get('reason') or '').strip()
  if not reason:
    container = str(bridge_container.get('container') or 'voice bridge container')
    reason = f'{container} not running'
  print(f'voice smoke failed: {reason}')
  raise SystemExit(0)

if bridge_smoke and str(bridge_smoke.get('status') or '') == 'fail':
  missing_states = bridge_smoke.get('missing_states') or []
  missing_event_types = bridge_smoke.get('missing_event_types') or []
  seen_states = bridge_smoke.get('seen_states') or []
  seen_event_types = bridge_smoke.get('seen_event_types') or []
  events = bridge_smoke.get('events') or []

  parts: list[str] = ['bridge smoke did not observe the required voice events']
  if missing_states:
    parts.append(f'missing states={fmt_list(missing_states)}')
  if missing_event_types:
    parts.append(f'missing event types={fmt_list(missing_event_types)}')
  if seen_states:
    parts.append(f'seen states={fmt_list(seen_states)}')
  if seen_event_types:
    parts.append(f'seen event types={fmt_list(seen_event_types)}')
  if not events:
    parts.append('no recent voice events captured')

  print('voice smoke failed: ' + '; '.join(parts))
  raise SystemExit(0)

if command_closure and str(command_closure.get('status') or '') == 'fail':
  reason = str(command_closure.get('reason') or 'voice command closure failed').strip()
  missing = command_closure.get('missing') or []
  if missing:
    reason = f'{reason}; missing={fmt_list(missing)}'
  print(f'voice smoke failed: {reason}')
  raise SystemExit(0)

if report:
  checks = report.get('checks')
  if isinstance(checks, list):
    for check in checks:
      if not isinstance(check, dict) or str(check.get('status') or '') != 'fail':
        continue
      reason = str(check.get('reason') or f"{check.get('name') or 'voice check'} failed").strip()
      print(f'voice smoke failed: {reason}')
      raise SystemExit(0)

stdout_text = stdout_path.read_text(encoding='utf-8', errors='replace').strip() if stdout_path.exists() else ''
if stdout_text:
  last_fail = ''
  for line in stdout_text.splitlines():
    if '[FAIL]' in line:
      last_fail = line.strip()
  if last_fail:
    print(f'voice smoke failed: {last_fail.replace("[FAIL]", "").strip()}')
    raise SystemExit(0)

print('voice smoke failed: unknown reason')
PY
}

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo -e "${RED}[FAIL]${NC} 未找到 compose 文件: $COMPOSE_FILE"
  exit 1
fi

FAILED=0
HOST_FAILED=0
LIVENESS_FAILED=0
READINESS_FAILED=0
declare -A RUNNING=()
OK_COUNT=0
TOTAL_COUNT=${#SERVICES[@]}
VOICE_FAILED=0
VOICE_CHECK_RAN=0
VOICE_STRICT=0

summarize_layer() {
  local label="$1"
  local failed_flag="$2"

  if [[ "$failed_flag" -eq 0 ]]; then
    print_ok "$label 通过"
  else
    print_fail "$label 失败"
  fi
}

section_header "Host-side 巡检"
check_local_env_overrides
check_runtime_paths
check_compose_drift || true

refresh_running_services

section_header "Liveness 巡检"
echo -e "${CYAN}目标服务: ${TOTAL_COUNT}${NC}"
for svc in "${SERVICES[@]}"; do
  if [[ -n "${RUNNING[$svc]:-}" ]]; then
    print_ok "$svc running"
    OK_COUNT=$((OK_COUNT + 1))
  else
    print_fail "$svc not running"
    mark_failure liveness
  fi
done
check_http_status "$MISSION_CONTROL_HEALTH_URL" "Mission Control API /health" liveness 200 || true

section_header "Readiness 巡检"
check_http_status "$MISSION_CONTROL_READY_URL" "Mission Control API /ready" readiness 200 || true
check_http_status "http://localhost:18920/" "Mission Control UI /" readiness 200 || true
check_chat_proxy_readiness || true

if bash "$PANOPTICON_DIR/tools/check_agent_endpoints.sh"; then
  print_ok "Agent endpoint readiness 通过"
else
  print_fail "Agent endpoint readiness 失败"
  mark_failure readiness
fi

check_container_health "$MISSION_CONTROL_AUTH_TOKEN" || true

if [[ "$CHECK_VOICE_E2E" == "1" ]]; then
  VOICE_STRICT=1
fi
if [[ "$CHECK_VOICE_E2E" != "0" ]]; then
  section_header "Voice Readiness (Optional)"
  if [[ -n "${RUNNING[$VOICE_CONTAINER]:-}" ]]; then
    VOICE_CHECK_RAN=1
    if [[ -f "$VOICE_ASSESS_SCRIPT" ]]; then
      VOICE_STDOUT_FILE="$(mktemp)"
      VOICE_REPORT_FILE="$(mktemp)"
      if python3 "$VOICE_ASSESS_SCRIPT" --skip-command-closure --output "$VOICE_REPORT_FILE" >"$VOICE_STDOUT_FILE" 2>&1; then
        cat "$VOICE_STDOUT_FILE"
        print_ok "voice assessment 通过"
      else
        if [[ "$VOICE_STRICT" -eq 1 ]]; then
          print_fail "$(voice_failure_summary "$VOICE_REPORT_FILE" "$VOICE_STDOUT_FILE")"
          mark_failure readiness
        else
          print_warn "$(voice_failure_summary "$VOICE_REPORT_FILE" "$VOICE_STDOUT_FILE")"
        fi
        VOICE_FAILED=1
      fi
      rm -f "$VOICE_STDOUT_FILE" "$VOICE_REPORT_FILE"
    else
      print_fail "voice assessment 脚本不存在: $VOICE_ASSESS_SCRIPT"
      if [[ "$VOICE_STRICT" -eq 1 ]]; then
        mark_failure readiness
      fi
      VOICE_FAILED=1
    fi
  else
    if [[ "$CHECK_VOICE_E2E" == "1" ]]; then
      print_fail "voice assessment 强制开启，但容器未运行: $VOICE_CONTAINER"
      mark_failure readiness
      VOICE_FAILED=1
    else
      print_skip "voice assessment (容器未运行: $VOICE_CONTAINER, CHECK_VOICE_E2E=auto)"
    fi
  fi
fi

section_header "Summary"
summarize_layer "Host-side" "$HOST_FAILED"
summarize_layer "Liveness" "$LIVENESS_FAILED"
summarize_layer "Readiness" "$READINESS_FAILED"
if [[ "$VOICE_CHECK_RAN" -eq 1 ]]; then
  if [[ "$VOICE_FAILED" -eq 1 ]]; then
    if [[ "$VOICE_STRICT" -eq 1 ]]; then
      print_fail "Voice readiness 失败（strict 模式阻断）"
    else
      print_warn "Voice readiness 有告警（auto 模式不阻断）"
    fi
  else
    print_ok "Voice readiness 通过"
  fi
elif [[ "$CHECK_VOICE_E2E" == "0" ]]; then
  print_skip "Voice readiness 已关闭 (CHECK_VOICE_E2E=0)"
else
  print_skip "Voice readiness 未执行"
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}结果: host-side、liveness、readiness 巡检通过；${OK_COUNT}/${TOTAL_COUNT} 个目标服务处于 running 状态${NC}"
  exit 0
fi

echo -e "${RED}结果: 分层巡检存在失败项，请优先按失败层排查:${NC}"
if [[ "$HOST_FAILED" -eq 1 ]]; then
  echo "bash panopticon/tools/rotate_gateway_tokens.sh"
  echo "python3 panopticon/tools/generate_panopticon.py --prune"
fi
if [[ "$LIVENESS_FAILED" -eq 1 || "$READINESS_FAILED" -eq 1 ]]; then
  echo "docker compose -f $COMPOSE_FILE ps"
fi
if [[ "$READINESS_FAILED" -eq 1 ]]; then
  echo "docker compose -f $COMPOSE_FILE logs --tail=80 mission-control-api mission-control-ui mission-control-gateway"
fi
if [[ "$VOICE_FAILED" -eq 1 ]]; then
  echo "docker compose -f $COMPOSE_FILE logs --tail=80 $VOICE_CONTAINER"
fi
exit 1
