#!/usr/bin/env bash
# Check nox gateway endpoints are reachable
# Usage: check_agent_endpoints.sh <agent_name>

set -uo pipefail

AGENT="${1:-nox}"
OK=0
FAIL=0

# Check OpenClaw node process is running (simplest reliable check in this env)
if pgrep -f "openclaw" &>/dev/null; then
    echo "OK: $AGENT process is running"
    ((OK++))
else
    echo "WARN: $AGENT process not found via pgrep"
    ((FAIL++))
fi

# Check gateway port is listening (try curl with short timeout as proxy)
if curl -fsS --max-time 2 http://localhost:26216/health >/dev/null 2>&1; then
    echo "OK: $AGENT gateway (port 26216) responding"
    ((OK++))
fi

echo "Result: ${OK} ok, ${FAIL} fail"
if [ "$OK" -eq 0 ]; then
    exit 1
fi
exit 0
