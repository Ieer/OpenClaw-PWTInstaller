#!/bin/bash
# start-brief-scheduler.sh — Start the email brief scheduler
# Run this after container restart to re-enable daily briefings
# Add to container's init/startup script for auto-restore

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$WORKSPACE/artifacts/email-brief/scheduler.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Scheduler already running (PID $OLD_PID)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

cd "$WORKSPACE"
nohup bash scripts/schedule_email_brief.sh > artifacts/email-brief/scheduler.log 2>&1 &
echo $! > "$PID_FILE"
echo "Scheduler started, PID $(cat "$PID_FILE")"
