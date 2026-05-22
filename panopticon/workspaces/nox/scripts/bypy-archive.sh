#!/bin/bash
# 文件自动归档到百度网盘 openclaw 目录
# 用法: ./scripts/bypy-archive.sh <本地文件路径> [目标子目录]
# 示例: ./scripts/bypy-archive.sh exports/report.pptx report
#       ./scripts/bypy-archive.sh exports/report.pptx  (自动归类到 report/)

set -euo pipefail

FILE="$1"
SUBDIR="${2:-}"

if [ ! -f "$FILE" ]; then
    echo "❌ 文件不存在: $FILE"
    exit 1
fi

FILENAME=$(basename "$FILE")
EXT="${FILENAME##*.}"

# 自动归类（如果不指定目标目录）
if [ -z "$SUBDIR" ]; then
    case "$EXT" in
        pptx|ppt|pdf|html|htm)
            SUBDIR="report" ;;
        xlsx|xls|csv|json)
            SUBDIR="data" ;;
        zip|tar|gz|7z)
            SUBDIR="archive" ;;
        md|txt|yaml|yml|toml)
            SUBDIR="skills" ;;
        *)
            SUBDIR="temp" ;;
    esac
fi

TARGET="/apps/bypy/openclaw/$SUBDIR/"

echo "📤 上传: $FILENAME → $TARGET"
python3 -m bypy upload "$FILE" "$TARGET" 2>&1 && echo "✅ 完成" || echo "❌ 失败"
