#!/bin/bash
# schedule_email_brief.sh
# 定时查收邮件并生成简报，早上6点 / 晚上8点 (Asia/Shanghai)
# 在容器内以 background exec 方式运行

SKILL_DIR="/home/node/.openclaw/workspace/skills/email-monitor"
OUT_DIR="/home/node/.openclaw/workspace/artifacts/email-brief"
TZ="Asia/Shanghai"

log() {
    echo "[$(TZ=$TZ date '+%Y-%m-%d %H:%M:%S')] $*"
}

run_check() {
    local slot="$1"  # "morning" or "evening"
    local ts
    ts=$(TZ=$TZ date '+%Y-%m-%d-%H%M')
    mkdir -p "$OUT_DIR"

    local outfile="$OUT_DIR/brief-${ts}-${slot}.json"

    log "🔍 Running $slot email check..."
    cd "$SKILL_DIR" || { log "ERROR: skill dir not found"; return 1; }

    node scripts/imap-monitor.js check --unseen --recent 12h 2>/dev/null > "$outfile"
    local status=$?

    if [ $status -ne 0 ]; then
        log "⚠️ Check failed (exit=$status), retrying without --recent..."
        node scripts/imap-monitor.js check --unseen --limit 10 2>/dev/null > "$outfile"
    fi

    log "✅ $slot brief saved -> $(basename "$outfile")"
    return 0
}

log "📬 Email Brief Scheduler started"
log "Scheduled: 06:00 / 20:00 CST (UTC+8)"

while true; do
    CURRENT_HOUR=$(TZ=$TZ date '+%H')
    CURRENT_MIN=$(TZ=$TZ date '+%M')

    # Run at 06:00 and 20:00 (within ±1 min window)
    if { [ "$CURRENT_HOUR" = "06" ] || [ "$CURRENT_HOUR" = "20" ]; } && [ "$CURRENT_MIN" = "00" ]; then
        if [ "$CURRENT_HOUR" = "06" ]; then
            run_check "morning"
        else
            run_check "evening"
        fi
        # Wait 2 minutes to avoid re-triggering
        sleep 120
    fi

    sleep 30
done
