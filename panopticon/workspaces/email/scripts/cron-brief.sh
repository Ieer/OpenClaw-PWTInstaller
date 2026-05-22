#!/bin/bash
# crontab wrapper for email brief
SKILL_DIR="/home/node/.openclaw/workspace/skills/email-monitor"
OUT_DIR="/home/node/.openclaw/workspace/artifacts/email-brief"
TZ="Asia/Shanghai"

SLOT="$1"
TS=$(TZ=$TZ date '+%Y-%m-%d-%H%M')
mkdir -p "$OUT_DIR"
cd "$SKILL_DIR" 2>/dev/null || exit 1
node scripts/imap-monitor.js check --unseen --limit 10 2>/dev/null > "$OUT_DIR/brief-${TS}-${SLOT}.json"
exit $?
