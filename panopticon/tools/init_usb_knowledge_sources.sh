#!/usr/bin/env bash
set -euo pipefail

USB_ROOT="${PANOPTICON_USB_HOST_PATH:-/media/pi/4A21-0000}"
KNOWLEDGE_SUBDIR="${PANOPTICON_KNOWLEDGE_USB_SUBDIR:-knowledge-sources}"
TARGET_DIR="${USB_ROOT%/}/${KNOWLEDGE_SUBDIR}"

mkdir -p "${TARGET_DIR}/incoming" \
         "${TARGET_DIR}/processed" \
         "${TARGET_DIR}/archive" \
         "${TARGET_DIR}/tmp"

cat > "${TARGET_DIR}/README.md" <<'EOF'
# USB Knowledge Raw Sources

该目录用于存放「知识原始资料」，供 mission-control-api 挂载后扫描/导入。

建议约定：

- incoming/: 新放入、待导入
- processed/: 已导入且仍活跃
- archive/: 已归档
- tmp/: OCR/解析中间文件

注意：

- 这是原始资料层，不建议在这里直接编辑结构化知识。
- 普通 U 盘建议仅存放原始资料与归档，不要放 Postgres 主库与热索引。
EOF

printf "[OK] initialized usb knowledge source directories: %s\n" "${TARGET_DIR}"
printf "[NEXT] place files under: %s\n" "${TARGET_DIR}/incoming"
printf "[NEXT] compose mount path in container: /data/knowledge-sources\n"
