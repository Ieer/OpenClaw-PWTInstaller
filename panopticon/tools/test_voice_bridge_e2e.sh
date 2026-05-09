#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"
MISSION_CONTROL_ENV_FILE="$PANOPTICON_DIR/env/mission-control.env"

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
    lines = path.read_text(encoding="utf-8").splitlines()
except OSError:
    raise SystemExit(0)

for raw_line in lines:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or "=" not in raw_line:
        continue
    current_key, current_value = raw_line.split("=", 1)
    if current_key.strip() == key:
        print(current_value.strip())
        break
PY
}

topic_path() {
  local raw="$1"
  raw="${raw#/}"
  printf '/%s' "$raw"
}

API_URL="${MC_API_URL:-http://127.0.0.1:18910}"
AGENT="${MC_VOICE_AGENT:-voice-engine}"
CONTAINER="${MC_VOICE_BRIDGE_CONTAINER:-mission-control-voice-bridge}"
TIMEOUT_S="${MC_VOICE_E2E_TIMEOUT_S:-12}"
AUTH_TOKEN="${MC_AUTH_TOKEN:-}"
if [[ -z "$AUTH_TOKEN" ]]; then
  AUTH_TOKEN="$(load_env_value "$MISSION_CONTROL_ENV_FILE" MC_AUTH_TOKEN)"
fi
TOPIC_WAKEUP="$(topic_path "${MC_VOICE_TOPIC_WAKEUP:-wakeup}")"
TOPIC_ASR="$(topic_path "${MC_VOICE_TOPIC_ASR:-asr}")"
TOPIC_TEXT_RESPONSE="$(topic_path "${MC_VOICE_TOPIC_TEXT_RESPONSE:-text_response}")"
TOPIC_TTS="$(topic_path "${MC_VOICE_TOPIC_TTS:-tts_topic}")"
export MC_API_URL="$API_URL"
export MC_AUTH_TOKEN="$AUTH_TOKEN"
export MC_VOICE_AGENT="$AGENT"
export MC_VOICE_E2E_TIMEOUT_S="$TIMEOUT_S"

if ! command -v docker >/dev/null 2>&1; then
  echo "[FAIL] docker not found"
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[FAIL] compose file not found: $COMPOSE_FILE"
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "[FAIL] container not running: ${CONTAINER}"
  echo "hint: docker compose -f $COMPOSE_FILE --profile voice up -d ${CONTAINER}"
  exit 1
fi

echo "[info] publishing synthetic ROS topics to ${CONTAINER}"
docker exec \
  -e TOPIC_WAKEUP="$TOPIC_WAKEUP" \
  -e TOPIC_ASR="$TOPIC_ASR" \
  -e TOPIC_TEXT_RESPONSE="$TOPIC_TEXT_RESPONSE" \
  -e TOPIC_TTS="$TOPIC_TTS" \
  "$CONTAINER" bash -lc '
source /opt/ros/humble/setup.bash
ros2 topic pub --once --wait-matching-subscriptions 1 "$TOPIC_WAKEUP" std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once --wait-matching-subscriptions 1 "$TOPIC_ASR" std_msgs/msg/String "{data: e2e voice bridge}"
ros2 topic pub --once --wait-matching-subscriptions 1 "$TOPIC_TEXT_RESPONSE" std_msgs/msg/String "{data: processing e2e}"
ros2 topic pub --once --wait-matching-subscriptions 1 "$TOPIC_TTS" std_msgs/msg/String "{data: speaking e2e}"
' >/tmp/mc_voice_bridge_pub.log 2>&1 || {
  echo "[FAIL] failed to publish ROS topics"
  cat /tmp/mc_voice_bridge_pub.log || true
  exit 1
}

echo "[info] waiting for voice events in feed-lite (timeout=${TIMEOUT_S}s)"
python - <<'PY'
import json
import os
import sys
import time
import urllib.request

api_url = os.getenv("MC_API_URL", "http://127.0.0.1:18910").rstrip("/")
agent = os.getenv("MC_VOICE_AGENT", "voice-engine")
timeout_s = int(os.getenv("MC_VOICE_E2E_TIMEOUT_S", "12"))
token = os.getenv("MC_AUTH_TOKEN", "").strip()

required = {"voice.state", "voice.asr.final", "voice.tts.start"}
deadline = time.time() + timeout_s
seen = set()
last_events = []

while time.time() < deadline:
    try:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(f"{api_url}/v1/feed-lite?limit=80", headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=3) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        arr = json.loads(payload)
        if not isinstance(arr, list):
            arr = []
    except Exception:
        time.sleep(0.4)
        continue

    last_events = [x for x in arr if str(x.get("agent") or "") == agent and str(x.get("type") or "").startswith("voice.")]
    seen = {str(x.get("type") or "") for x in last_events}
    if required.issubset(seen):
        break
    time.sleep(0.4)

print(f"[info] seen voice types: {sorted(seen)}")
for item in last_events[:10]:
    print(f"  - {item.get('type')} {item.get('created_at')}")

missing = sorted(required - seen)
if missing:
    print(f"[FAIL] missing required voice events: {missing}")
    sys.exit(1)

print("[PASS] voice bridge e2e verified")
PY
