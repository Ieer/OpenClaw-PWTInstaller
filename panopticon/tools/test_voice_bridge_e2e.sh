#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"

API_URL="${MC_API_URL:-http://127.0.0.1:18910}"
AGENT="${MC_VOICE_AGENT:-voice-engine}"
CONTAINER="${MC_VOICE_BRIDGE_CONTAINER:-mission-control-voice-bridge}"
TIMEOUT_S="${MC_VOICE_E2E_TIMEOUT_S:-12}"

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
docker exec "$CONTAINER" bash -lc '
source /opt/ros/humble/setup.bash
ros2 topic pub -1 /wakeup std_msgs/msg/Bool "{data: true}"
ros2 topic pub -1 /asr std_msgs/msg/String "{data: e2e voice bridge}"
ros2 topic pub -1 /text_response std_msgs/msg/String "{data: processing e2e}"
ros2 topic pub -1 /tts_topic std_msgs/msg/String "{data: speaking e2e}"
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

required = {"voice.state", "voice.asr.final", "voice.tts.start"}
deadline = time.time() + timeout_s
seen = set()
last_events = []

while time.time() < deadline:
    try:
        with urllib.request.urlopen(f"{api_url}/v1/feed-lite?limit=80", timeout=3) as resp:
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
