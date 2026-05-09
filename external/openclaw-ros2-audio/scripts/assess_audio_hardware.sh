#!/usr/bin/env bash
set -euo pipefail

RECORD_SECONDS="${OPENCLAW_AUDIO_PROBE_RECORD_SECONDS:-3}"
SAMPLE_RATE="${OPENCLAW_AUDIO_PROBE_SAMPLE_RATE:-16000}"
CHANNELS="${OPENCLAW_AUDIO_PROBE_CHANNELS:-1}"
INPUT_DEVICE="${OPENCLAW_AUDIO_INPUT_DEVICE:-}"
OUTPUT_DEVICE="${OPENCLAW_AUDIO_OUTPUT_DEVICE:-}"
RECORD_FILE="${OPENCLAW_AUDIO_PROBE_RECORD_FILE:-/tmp/openclaw-audio-probe.wav}"
PLAY_RECORDING="${OPENCLAW_AUDIO_PROBE_PLAY:-0}"
TEST_TTS="${OPENCLAW_AUDIO_PROBE_TTS:-0}"
TTS_TEXT="${OPENCLAW_AUDIO_PROBE_TTS_TEXT:-语音硬件测试成功}"
TTS_VOICE="${OPENCLAW_TTS_VOICE:-zh-CN-XiaoyiNeural}"
TTS_FILE="${OPENCLAW_AUDIO_PROBE_TTS_FILE:-/tmp/openclaw-audio-probe.mp3}"
MIN_PEAK="${OPENCLAW_AUDIO_PROBE_MIN_PEAK:-200}"

status=0

has_command() {
  command -v "$1" >/dev/null 2>&1
}

section() {
  printf '\n== %s ==\n' "$1"
}

section "audio devices"
if has_command arecord; then
  arecord -l || status=1
  arecord -L | sed -n '1,80p' || true
else
  echo "[FAIL] arecord not found; install alsa-utils"
  status=1
fi

if has_command aplay; then
  aplay -l || true
else
  echo "[warn] aplay not found; playback probe is unavailable"
fi

if has_command pactl; then
  pactl list short sources || true
  pactl list short sinks || true
else
  echo "[info] pactl not found; skipping PulseAudio/PipeWire list"
fi

section "record microphone"
if has_command arecord; then
  record_args=(-q -f S16_LE -r "$SAMPLE_RATE" -c "$CHANNELS" -d "$RECORD_SECONDS" -t wav)
  if [[ -n "$INPUT_DEVICE" ]]; then
    record_args+=(-D "$INPUT_DEVICE")
  fi
  if arecord "${record_args[@]}" "$RECORD_FILE"; then
    bytes=$(wc -c <"$RECORD_FILE" | tr -d ' ')
    echo "[PASS] recorded $RECORD_FILE (${bytes} bytes)"
    python3 - "$RECORD_FILE" "$MIN_PEAK" <<'PY'
import math
import struct
import sys
import wave

path = sys.argv[1]
min_peak = int(sys.argv[2])
with wave.open(path, "rb") as wav:
    channels = wav.getnchannels()
    width = wav.getsampwidth()
    rate = wav.getframerate()
    frames = wav.readframes(wav.getnframes())
    frame_count = wav.getnframes()

if width != 2:
    print(f"[warn] skip amplitude stats: expected 16-bit PCM, got sample width {width}")
    raise SystemExit(0)

samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
peak = max((abs(sample) for sample in samples), default=0)
rms = math.sqrt(sum(sample * sample for sample in samples) / max(len(samples), 1))
duration = frame_count / rate if rate else 0.0
print(f"[info] wav stats: duration={duration:.2f}s rate={rate}Hz channels={channels} peak={peak} rms={rms:.1f}")
if peak < min_peak:
    print(f"[FAIL] microphone signal peak {peak} is below threshold {min_peak}; check input device or speak during probe")
    raise SystemExit(2)
PY
  else
    echo "[FAIL] microphone recording failed"
    status=1
  fi
fi

if [[ "$PLAY_RECORDING" == "1" ]]; then
  section "play recording"
  if has_command aplay; then
    play_args=()
    if [[ -n "$OUTPUT_DEVICE" ]]; then
      play_args+=(-D "$OUTPUT_DEVICE")
    fi
    aplay "${play_args[@]}" "$RECORD_FILE" || status=1
  else
    echo "[FAIL] aplay not found"
    status=1
  fi
fi

if [[ "$TEST_TTS" == "1" ]]; then
  section "edge-tts playback"
  if ! has_command edge-tts; then
    echo "[FAIL] edge-tts not found; run with OPENCLAW_ROS_INSTALL_AUDIO_DEPS=1"
    status=1
  else
    edge-tts --voice "$TTS_VOICE" --text "$TTS_TEXT" --write-media "$TTS_FILE"
    echo "[PASS] generated $TTS_FILE"
    if has_command mpg123; then
      mpg123_args=(-q)
      if [[ -n "$OUTPUT_DEVICE" ]]; then
        mpg123_args+=(-a "$OUTPUT_DEVICE")
      fi
      mpg123 "${mpg123_args[@]}" "$TTS_FILE" || status=1
    elif has_command ffplay; then
      ffplay -nodisp -autoexit -loglevel error "$TTS_FILE" || status=1
    else
      echo "[warn] no mp3 player found; install mpg123 or ffmpeg"
    fi
  fi
fi

exit "$status"