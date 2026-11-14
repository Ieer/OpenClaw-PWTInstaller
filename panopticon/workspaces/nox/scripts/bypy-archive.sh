#!/bin/bash
# bypy-archive.sh — 扫描 exports/ 和 outbox/ 新文件，自动上传到百度网盘
# 不依赖 LLM，直接执行
# Usage: bash scripts/bypy-archive.sh
# ⚠️ 路径规则: bypy 根目录为 /apps/bypy, 目标路径必须用相对路径(如 openclaw/report/),
#    绝对路径(如 /apps/bypy/openclaw/report/)会被二次拼接导致落错位置(2026-08-07 已修复迁移)

set -e

WORKSPACE="/home/node/.openclaw/workspace"
# bypy 装在 workspace 内持久目录(容器重启不丢)
export PYTHONPATH="$WORKSPACE/runtime-assets/pylibs:${PYTHONPATH:-}"
EXPORTS_DIR="$WORKSPACE/exports"
OUTBOX_DIR="$WORKSPACE/outbox"
BYPY="python3 -m bypy"
NOW=$(date +%s)
CUTOFF=$((NOW - 86400))  # 24小时内
LOG_DIR="$WORKSPACE/state"
LOG_FILE="$LOG_DIR/bypy-archive-$(date +%Y-%m-%d).log"
UPLOADED=0
SKIPPED=0
FAILED=0

mkdir -p "$LOG_DIR"

echo "=== bypy-archive $(date -u '+%Y-%m-%dT%H:%M:%SZ') ===" | tee -a "$LOG_FILE"

# --- upload_file <filepath> <category> ---
upload_file() {
    local filepath="$1"
    local category="$2"
    local filename
    filename=$(basename "$filepath")

    # 映射分类到目标路径 (相对路径, bypy 根为 /apps/bypy)
    case "$category" in
        report)  TARGET="openclaw/report/" ;;
        data)    TARGET="openclaw/data/" ;;
        skills)  TARGET="openclaw/skills/" ;;
        archive) TARGET="openclaw/archive/" ;;
        *)       TARGET="openclaw/temp/" ;;
    esac

    echo "  → Uploading $filename to $TARGET" | tee -a "$LOG_FILE"
    if $BYPY upload "$filepath" "$TARGET" >> "$LOG_FILE" 2>&1; then
        echo "  ✅ Uploaded: $filename" | tee -a "$LOG_FILE"
        UPLOADED=$((UPLOADED + 1))
        # 删除已上传文件（保留 .html）
        case "$filename" in
            *.html)
                echo "  → Preserving $filename (.html kept)" | tee -a "$LOG_FILE"
                ;;
            *)
                rm -f "$filepath"
                echo "  → Removed local: $filename" | tee -a "$LOG_FILE"
                ;;
        esac
    else
        echo "  ❌ Failed: $filename" | tee -a "$LOG_FILE"
        FAILED=$((FAILED + 1))
    fi
}

# --- classify <filename> ---
classify() {
    local fname="$1"
    case "$fname" in
        *.pptx|*.ppt|*.pdf|*.html) echo "report" ;;
        *.xlsx|*.xls|*.csv|*.json) echo "data" ;;
        *.zip|*.tar|*.tar.gz|*.gz) echo "archive" ;;
        *.md|*.txt|*.yaml|*.yml)   echo "skills" ;;
        *)                         echo "temp" ;;
    esac
}

# --- scan <directory> ---
scan() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        echo "  Directory not found: $dir" | tee -a "$LOG_FILE"
        return
    fi
    echo "  Scanning: $dir" | tee -a "$LOG_FILE"
    while IFS= read -r -d '' file; do
        ftime=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)
        if [ "$ftime" -ge "$CUTOFF" ]; then
            cat=$(classify "$(basename "$file")")
            upload_file "$file" "$cat"
        fi
    done < <(find "$dir" -maxdepth 1 -type f -newert "$(date -d @$CUTOFF +%Y%m%d%H%M.%S)" -print0 2>/dev/null || find "$dir" -maxdepth 1 -type f -print0 2>/dev/null | while IFS= read -r -d '' f; do ft=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null); if [ "$ft" -ge "$CUTOFF" ]; then echo -n "$f"$'\0'; fi; done)
}

scan "$EXPORTS_DIR"
scan "$OUTBOX_DIR"

# --- summary ---
echo "---" | tee -a "$LOG_FILE"
echo "📊 结果: ✅ $UPLOADED 上传成功 | ❌ $FAILED 失败 | ⏭️ $SKIPPED 跳过" | tee -a "$LOG_FILE"
echo "=== Done ===" | tee -a "$LOG_FILE"

exit $FAILED
