#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"

API_URL="${MC_API_URL:-http://127.0.0.1:18910}"
AGENT="${MC_VOICE_AGENT:-voice-engine}"
CONTAINER="${MC_VOICE_BRIDGE_CONTAINER:-mission-control-voice-bridge}"
TIMEOUT_S="${MC_VOICE_LIVE_TIMEOUT_S:-60}"
EXPECT_TYPES_RAW="${MC_VOICE_EXPECT_EVENT_TYPES:-voice.state,voice.asr.final}"
TOPIC_WAKEUP="/${MC_VOICE_TOPIC_WAKEUP:-wakeup}"
TOPIC_ASR="/${MC_VOICE_TOPIC_ASR:-asr}"
TOPIC_TEXT_RESPONSE="/${MC_VOICE_TOPIC_TEXT_RESPONSE:-text_response}"
TOPIC_TTS="/${MC_VOICE_TOPIC_TTS:-tts_topic}"

if ! command -v docker >/dev/null 2>&1; then
  echo -e "${RED}[FAIL]${NC} docker 未安装或不在 PATH"
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo -e "${RED}[FAIL]${NC} 未找到 compose 文件: $COMPOSE_FILE"
  exit 1
fi

echo -e "${CYAN}=== Voice Bridge Live 检查 ===${NC}"
echo "API_URL=$API_URL"
echo "AGENT=$AGENT"
echo "CONTAINER=$CONTAINER"
echo "TIMEOUT_S=$TIMEOUT_S"
echo "EXPECTED=$EXPECT_TYPES_RAW"
echo

CONTAINER_RUNNING=0
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  CONTAINER_RUNNING=1
  echo -e "${GREEN}[OK]${NC} 容器运行中: $CONTAINER"
else
  echo -e "${YELLOW}[WARN]${NC} 容器未运行: $CONTAINER"
  echo "hint: docker compose -f $COMPOSE_FILE --profile voice up -d $CONTAINER"
fi

if [[ "$CONTAINER_RUNNING" -eq 1 ]]; then
  echo
  echo -e "${CYAN}=== ROS2 话题可见性 ===${NC}"
  docker exec "$CONTAINER" bash -lc '
source /opt/ros/humble/setup.bash
topics=$(ros2 topic list 2>/dev/null || true)
echo "$topics"
' | while IFS= read -r line; do
    [[ -n "$line" ]] && echo "  $line"
  done

  for topic in "$TOPIC_WAKEUP" "$TOPIC_ASR" "$TOPIC_TEXT_RESPONSE" "$TOPIC_TTS"; do
    if docker exec "$CONTAINER" bash -lc "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep -qx '$topic'"; then
      echo -e "${GREEN}[OK]${NC} 发现话题 $topic"
    else
      echo -e "${YELLOW}[WARN]${NC} 未发现话题 $topic"
    fi
  done
fi

echo
echo -e "${CYAN}=== 监听 Mission Control 语音事件 ===${NC}"
python - <<'PY'
import json
import os
import sys
import time
import urllib.request

api_url = os.getenv("MC_API_URL", "http://127.0.0.1:18910").rstrip("/")
agent = os.getenv("MC_VOICE_AGENT", "voice-engine")
timeout_s = int(os.getenv("MC_VOICE_LIVE_TIMEOUT_S", "60"))
required = {item.strip() for item in os.getenv("MC_VOICE_EXPECT_EVENT_TYPES", "voice.state,voice.asr.final").split(",") if item.strip()}

deadline = time.time() + timeout_s
seen = set()
last_events = []

while time.time() < deadline:
    try:
        with urllib.request.urlopen(f"{api_url}/v1/feed-lite?limit=120", timeout=3) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        arr = json.loads(payload)
        if not isinstance(arr, list):
            arr = []
    except Exception:
        time.sleep(0.5)
        continue

    filtered = [
        item for item in arr
        if str(item.get("agent") or "") == agent and str(item.get("type") or "").startswith("voice.")
    ]
    filtered.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    last_events = filtered[:12]
    seen = {str(item.get("type") or "") for item in filtered}
    if required and required.issubset(seen):
        break
    time.sleep(0.5)

print(f"[info] seen voice types: {sorted(seen)}")
for item in last_events:
    print(f"  - {item.get('type')} {item.get('created_at')}")

missing = sorted(required - seen)
if missing:
    print(f"[FAIL] missing expected live voice events: {missing}")
    sys.exit(1)

print("[PASS] live voice events observed")
PY

echo
echo -e "${GREEN}[DONE]${NC} 如已看到 live voice events，可继续说一条带前缀命令验证 Mission Control 直控。"