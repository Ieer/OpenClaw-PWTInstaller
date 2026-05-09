#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "[FAIL] ros2 not found. Source your ROS2 setup first."
  exit 1
fi

if [[ -f "$WORKSPACE_DIR/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "$WORKSPACE_DIR/install/setup.bash"
fi

echo "[info] publishing one manual turn"
ros2 run openclaw_voice_stack manual_turn_node "$@"

echo "[info] current topics"
ros2 topic list | grep -E '^/(wakeup|asr|text_response|tts_topic|tts_request)$' || true

echo "[done] if mission-control-voice-bridge is running, use panopticon/tools/check_voice_bridge_live.sh to verify feed events."
