#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$WORKSPACE_DIR/../.." && pwd)"
IMAGE="${OPENCLAW_ROS_IMAGE:-ros:humble-ros-base}"
CONTAINER_NAME="${OPENCLAW_ROS_CONTAINER_NAME:-openclaw-ros2-audio-dev}"
BRIDGE_CONTAINER="${MC_VOICE_BRIDGE_CONTAINER:-mission-control-voice-bridge}"
DEFAULT_CMD='ros2 run openclaw_voice_stack manual_turn_node --ros-args -p delay_seconds:=1.0 -p wait_for_subscriptions:=true -p subscription_wait_seconds:=8.0'
RUN_CMD="${*:-$DEFAULT_CMD}"
AUDIO_UID="${AUDIO_UID:-$(id -u)}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[FAIL] docker not found"
  exit 1
fi

DOCKER_ARGS=(--rm --name "$CONTAINER_NAME")

if docker ps --format '{{.Names}}' | grep -qx "$BRIDGE_CONTAINER"; then
  DOCKER_ARGS+=(--network "container:$BRIDGE_CONTAINER")
  echo "[info] sharing network namespace with $BRIDGE_CONTAINER for ROS2 DDS discovery"
else
  echo "[warn] $BRIDGE_CONTAINER is not running; using default Docker network"
fi

if [[ -d /dev/snd ]]; then
  DOCKER_ARGS+=(--device /dev/snd)
fi

if [[ "${OPENCLAW_ROS_ENABLE_USB:-0}" == "1" && -d /dev/bus/usb ]]; then
  DOCKER_ARGS+=(--device /dev/bus/usb)
fi

if [[ -n "${OPENCLAW_ROS_SERIAL_DEVICES:-}" ]]; then
  for serial_device in ${OPENCLAW_ROS_SERIAL_DEVICES}; do
    if [[ -e "$serial_device" ]]; then
      DOCKER_ARGS+=(--device "$serial_device")
    else
      echo "[warn] serial device not found: $serial_device"
    fi
  done
fi

PULSE_DIR="/run/user/$AUDIO_UID/pulse"
if [[ -S "$PULSE_DIR/native" ]]; then
  DOCKER_ARGS+=(
    -e "PULSE_SERVER=unix:$PULSE_DIR/native"
    -e SDL_AUDIODRIVER=pulse
    -v "$PULSE_DIR:$PULSE_DIR:ro"
  )
  if [[ -d "$HOME/.config/pulse" ]]; then
    DOCKER_ARGS+=(-v "$HOME/.config/pulse:/root/.config/pulse:ro")
  fi
else
  DOCKER_ARGS+=(-e SDL_AUDIODRIVER=alsa)
fi

if [[ -f "$REPO_ROOT/panopticon/env/mission-control.env" ]]; then
  DOCKER_ARGS+=(--env-file "$REPO_ROOT/panopticon/env/mission-control.env")
fi

DOCKER_ARGS+=(
  -e "MC_API_URL=${MC_API_URL:-http://mission-control-api:9090}"
  -e "OPENCLAW_ASR_HTTP_URL=${OPENCLAW_ASR_HTTP_URL:-}"
  -e "OPENCLAW_ASR_HTTP_TOKEN=${OPENCLAW_ASR_HTTP_TOKEN:-}"
  -e "OPENCLAW_AUDIO_INPUT_DEVICE=${OPENCLAW_AUDIO_INPUT_DEVICE:-}"
  -e "OPENCLAW_AUDIO_OUTPUT_DEVICE=${OPENCLAW_AUDIO_OUTPUT_DEVICE:-}"
  -e "OPENCLAW_AUDIO_PROBE_RECORD_SECONDS=${OPENCLAW_AUDIO_PROBE_RECORD_SECONDS:-}"
  -e "OPENCLAW_AUDIO_PROBE_SAMPLE_RATE=${OPENCLAW_AUDIO_PROBE_SAMPLE_RATE:-}"
  -e "OPENCLAW_AUDIO_PROBE_CHANNELS=${OPENCLAW_AUDIO_PROBE_CHANNELS:-}"
  -e "OPENCLAW_AUDIO_PROBE_PLAY=${OPENCLAW_AUDIO_PROBE_PLAY:-}"
  -e "OPENCLAW_AUDIO_PROBE_TTS=${OPENCLAW_AUDIO_PROBE_TTS:-}"
  -e "OPENCLAW_AUDIO_PROBE_TTS_TEXT=${OPENCLAW_AUDIO_PROBE_TTS_TEXT:-}"
  -e "OPENCLAW_AUDIO_PROBE_MIN_PEAK=${OPENCLAW_AUDIO_PROBE_MIN_PEAK:-}"
  -e "OPENCLAW_TTS_VOICE=${OPENCLAW_TTS_VOICE:-zh-CN-XiaoyiNeural}"
  -e "DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY:-}"
  -e "OPENCLAW_TONGYI_ASR_MODEL=${OPENCLAW_TONGYI_ASR_MODEL:-paraformer-realtime-8k-v2}"
  -e "OPENCLAW_TONGYI_ASR_SAMPLE_RATE=${OPENCLAW_TONGYI_ASR_SAMPLE_RATE:-16000}"
  -e "OPENCLAW_ROS_INSTALL_TONGYI_ASR_DEPS=${OPENCLAW_ROS_INSTALL_TONGYI_ASR_DEPS:-0}"
  -e "FASTDDS_BUILTIN_TRANSPORTS=${FASTDDS_BUILTIN_TRANSPORTS:-UDPv4}"
  -e "OPENCLAW_ROS_INSTALL_AUDIO_DEPS=${OPENCLAW_ROS_INSTALL_AUDIO_DEPS:-0}"
  -v "$WORKSPACE_DIR:/ws-src:ro"
  -w /tmp/openclaw-ros2-audio
)

docker run "${DOCKER_ARGS[@]}" "$IMAGE" bash -lc "
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v colcon >/dev/null 2>&1 || ! python3 -c 'import yaml' >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends python3-colcon-common-extensions python3-yaml
fi

if [[ "\${OPENCLAW_ROS_INSTALL_AUDIO_DEPS:-0}" == "1" ]]; then
  apt-get update
  apt-get install -y --no-install-recommends python3-pip alsa-utils espeak-ng ffmpeg mpg123 libsndfile1 portaudio19-dev
fi

cp -a /ws-src/. /tmp/openclaw-ros2-audio/
if ! python3 -c 'import yaml' >/dev/null 2>&1; then
  python3 -m pip install --no-cache-dir -r requirements.txt
fi
if [[ "\${OPENCLAW_ROS_INSTALL_AUDIO_DEPS:-0}" == "1" ]] && ! command -v edge-tts >/dev/null 2>&1; then
  python3 -m pip install --no-cache-dir -r requirements-audio.txt
fi
if [[ "\${OPENCLAW_ROS_INSTALL_TONGYI_ASR_DEPS:-0}" == "1" ]] && ! python3 -c 'import dashscope' >/dev/null 2>&1; then
  python3 -m pip install --no-cache-dir -r requirements-asr-dashscope.txt
fi
colcon build --symlink-install
set +u
source install/setup.bash
set -u
$RUN_CMD
"
