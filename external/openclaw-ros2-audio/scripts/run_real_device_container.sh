#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${OPENCLAW_ROS_REAL_DEVICE_CONFIG:-src/openclaw_voice_stack/config/real-device.http-edge.example.yaml}"
YAHBOOM_TONGYI_CONFIG="${YAHBOOM_TONGYI_CONFIG:-/home/pi/yahboom_ws/src/largemodel/config/large_model_interface.yaml}"

load_scalar_config() {
  local file="$1"
  local key="$2"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  python3 - "$file" "$key" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or ":" not in line:
        continue
    current_key, raw_value = line.split(":", 1)
    if current_key.strip() != key:
        continue
    value = raw_value.split("#", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    print(value.strip())
    break
PY
}

export OPENCLAW_ROS_INSTALL_AUDIO_DEPS="${OPENCLAW_ROS_INSTALL_AUDIO_DEPS:-1}"
export OPENCLAW_START_TONGYI_ASR_SERVICE="${OPENCLAW_START_TONGYI_ASR_SERVICE:-1}"

if [[ "${OPENCLAW_START_TONGYI_ASR_SERVICE}" == "1" ]]; then
  export OPENCLAW_ROS_INSTALL_TONGYI_ASR_DEPS="${OPENCLAW_ROS_INSTALL_TONGYI_ASR_DEPS:-1}"
  export OPENCLAW_ASR_HTTP_URL="${OPENCLAW_ASR_HTTP_URL:-http://127.0.0.1:18081/asr}"
  if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
    export DASHSCOPE_API_KEY="$(load_scalar_config "$YAHBOOM_TONGYI_CONFIG" tongyi_api_key)"
  fi
  if [[ -z "${OPENCLAW_TONGYI_ASR_MODEL:-}" ]]; then
    export OPENCLAW_TONGYI_ASR_MODEL="$(load_scalar_config "$YAHBOOM_TONGYI_CONFIG" oline_asr_model)"
  fi
  if [[ -z "${OPENCLAW_TONGYI_ASR_SAMPLE_RATE:-}" ]]; then
    export OPENCLAW_TONGYI_ASR_SAMPLE_RATE="$(load_scalar_config "$YAHBOOM_TONGYI_CONFIG" oline_asr_sample_rate)"
  fi
  if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
    echo "[FAIL] DASHSCOPE_API_KEY is empty and no tongyi_api_key was loaded from $YAHBOOM_TONGYI_CONFIG"
    echo "       Export DASHSCOPE_API_KEY, or set YAHBOOM_TONGYI_CONFIG to the Tongyi config file."
    exit 1
  fi
fi

if [[ -z "${OPENCLAW_ASR_HTTP_URL:-}" ]]; then
  echo "[warn] OPENCLAW_ASR_HTTP_URL is empty; asr_node will fail until an HTTP ASR endpoint is configured"
fi

if [[ "${OPENCLAW_START_TONGYI_ASR_SERVICE}" == "1" ]]; then
  exec "$SCRIPT_DIR/run_humble_container.sh" \
    'python3 scripts/serve_dashscope_asr.py --host 127.0.0.1 --port 18081 & exec ros2 launch openclaw_voice_stack openclaw_voice_stack.launch.py config:='"$CONFIG_PATH"
else
  exec "$SCRIPT_DIR/run_humble_container.sh" \
    ros2 launch openclaw_voice_stack openclaw_voice_stack.launch.py \
    config:="$CONFIG_PATH"
fi