#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
SERVICE_NAME="openclaw-cnim.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
DOCKER_BIN="$(command -v docker || true)"
SERVICE_STACK="openclaw-gateway"

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

if [[ "${1:-}" == "--disable" ]]; then
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

$SUDO tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=OpenClaw Docker CN-IM Service
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=$DOCKER_BIN compose -f $COMPOSE_FILE up -d $SERVICE_STACK
ExecStop=$DOCKER_BIN compose -f $COMPOSE_FILE stop $SERVICE_STACK
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

echo "[INFO] 重新加载并启用服务"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "$SERVICE_NAME"

echo "[OK] OpenClaw-Docker-CN-IM 开机自启已启用"
echo "[INFO] 状态检查: systemctl status $SERVICE_NAME --no-pager"
echo "[INFO] 停用命令: bash external/OpenClaw-Docker-CN-IM/tools/setup_openclaw_autostart.sh --disable"
