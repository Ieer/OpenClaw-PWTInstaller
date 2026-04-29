#!/bin/bash
# inner-map-sync.sh
# Inner-Map 知识库同步脚本
# 用途：同步 workspace/sources/inner-map-skill-router 到 U 盘

set -e

WORKSPACE="/home/node/.openclaw/workspace/sources/inner-map-skill-router"
USB="/mnt/usb/inner-map-skill-router"
LOG_DIR="$WORKSPACE/sync-logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建日志目录
mkdir -p "$LOG_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1"
}

# 检查源目录
if [ ! -d "$WORKSPACE" ]; then
    echo -e "${RED}错误：workspace 目录不存在: $WORKSPACE${NC}"
    exit 1
fi

# 检查 U 盘
if [ ! -d "$USB" ]; then
    echo -e "${RED}错误：U 盘未挂载: $USB${NC}"
    exit 1
fi

log "开始同步..."
log "源: $WORKSPACE"
log "目标: $USB"

# 同步主文件（排除软链接）
log "同步主文件..."
cp -v "$WORKSPACE/skills.md" "$USB/" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"
cp -v "$WORKSPACE/README.md" "$USB/" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"
cp -v "$WORKSPACE/skills-architecture.md" "$USB/" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"

# 同步子技能文件
log "同步子技能文件..."
for skill in skills-dialog-management.md skills-communication-coach_20260412_164523.md \
              skills-excellence-calibration.md skills-inner-map-self-management.md \
              skills-test-dialogs.md; do
    cp -v "$WORKSPACE/$skill" "$USB/" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"
done

# 同步 knowledge 目录（递归）
log "同步 knowledge 目录..."
if command -v rsync &> /dev/null; then
    rsync --recursive --verbose --itemize-changes --delete \
          "$WORKSPACE/knowledge/" "$USB/knowledge/" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"
else
    log "rsync 不可用，改用 cp -r..."
    rm -rf "$USB/knowledge/"/* 2>/dev/null || true
    cp -rv "$WORKSPACE/knowledge/"* "$USB/knowledge/" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"
fi

# 处理 SKILL.md 软链接（U 盘 exfat 不支持软链接）
if [ -L "$WORKSPACE/SKILL.md" ]; then
    log "处理 SKILL.md 软链接（U 盘不支持软链接，复制内容）..."
    cp -v "$WORKSPACE/skills.md" "$USB/SKILL.md" 2>&1 | tee -a "$LOG_DIR/sync-$TIMESTAMP.log"
fi

# 统计
WORKSPACE_FILES=$(find "$WORKSPACE" -type f | wc -l)
USB_FILES=$(find "$USB" -type f | wc -l)

log "同步完成！"
log "Workspace 文件数: $WORKSPACE_FILES"
log "U 盘文件数: $USB_FILES"
log "日志: $LOG_DIR/sync-$TIMESTAMP.log"

echo -e "${GREEN}✓ Inner-Map 同步完成${NC}"
echo ""
echo "如需查看差异："
echo "  diff -qr $WORKSPACE $USB"
echo ""
echo "如需从 U 盘恢复到 workspace："
echo "  $0 --reverse"
