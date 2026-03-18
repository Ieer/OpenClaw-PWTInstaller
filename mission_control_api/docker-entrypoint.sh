#!/bin/sh
set -eu

MAX_RETRIES="${MC_DB_MIGRATION_MAX_RETRIES:-30}"
SLEEP_SECONDS="${MC_DB_MIGRATION_RETRY_INTERVAL_SECONDS:-2}"

attempt=1
while [ "$attempt" -le "$MAX_RETRIES" ]; do
  if alembic upgrade head; then
    break
  fi

  if [ "$attempt" -eq "$MAX_RETRIES" ]; then
    echo "[mission-control-api] alembic migration failed after ${MAX_RETRIES} attempts" >&2
    exit 1
  fi

  echo "[mission-control-api] migration attempt ${attempt}/${MAX_RETRIES} failed, retry in ${SLEEP_SECONDS}s..." >&2
  sleep "$SLEEP_SECONDS"
  attempt=$((attempt + 1))
done

exec uvicorn app.main:app --host 0.0.0.0 --port 9090
