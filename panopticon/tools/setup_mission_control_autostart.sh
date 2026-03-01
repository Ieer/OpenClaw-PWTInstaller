#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PANOPTICON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PANOPTICON_DIR/.." && pwd)"
COMPOSE_FILE="$PANOPTICON_DIR/docker-compose.panopticon.yml"
SERVICE_NAME="panopticon-mission-control.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
DOCKER_BIN="$(command -v docker || true)"
WITH_VOICE=0

usage() {
  cat <<'EOF'
Usage:
  bash panopticon/tools/setup_mission_control_autostart.sh [--with-voice]
  bash panopticon/tools/setup_mission_control_autostart.sh --disable

Options:
  --with-voice   启用开机自启时同时带上 docker compose voice profile
  --disable      移除开机自启服务
EOF
}

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

for arg in "$@"; do
  case "$arg" in
    --with-voice)
      WITH_VOICE=1
      ;;
    --disable)
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] 未知参数: $arg"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$DOCKER_BIN" ]]; then
  echo "[ERROR] docker 未安装或不在 PATH 中"
  exit 1
fi

if ! "$DOCKER_BIN" compose version >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 docker compose 插件"
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[ERROR] 未找到 compose 文件: $COMPOSE_FILE"
  exit 1
fi

if [[ " ${*} " == *" --disable "* ]]; then
  if [[ $EUID -ne 0 ]]; then
    sudo systemctl disable --now "$SERVICE_NAME" || true
    sudo rm -f "$SERVICE_PATH"
    sudo systemctl daemon-reload
  else
    systemctl disable --now "$SERVICE_NAME" || true
    rm -f "$SERVICE_PATH"
    systemctl daemon-reload
  fi
  echo "[OK] 已移除开机自启: $SERVICE_NAME"
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

echo "[INFO] 写入 systemd 服务: $SERVICE_PATH"

PROFILE_ARGS=""
VOICE_SERVICE=""
if [[ "$WITH_VOICE" -eq 1 ]]; then
  PROFILE_ARGS="--profile voice"
  VOICE_SERVICE=" mission-control-voice-bridge"
fi

$SUDO tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=Panopticon Mission Control Services
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$REPO_ROOT
ExecStart=$DOCKER_BIN compose -f $COMPOSE_FILE $PROFILE_ARGS up -d ${SERVICES[*]}$VOICE_SERVICE
ExecStop=$DOCKER_BIN compose -f $COMPOSE_FILE $PROFILE_ARGS stop ${SERVICES[*]}$VOICE_SERVICE
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

echo "[INFO] 重新加载并启用服务"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "$SERVICE_NAME"

echo "[OK] Mission Control 开机自启已启用"
if [[ "$WITH_VOICE" -eq 1 ]]; then
  echo "[INFO] 已启用 voice profile 自启（包含 mission-control-voice-bridge）"
else
  echo "[INFO] 未启用 voice profile（如需启用请加 --with-voice）"
fi
echo "[INFO] 状态检查: systemctl status $SERVICE_NAME --no-pager"
echo "[INFO] 停用命令: bash panopticon/tools/setup_mission_control_autostart.sh --disable"
