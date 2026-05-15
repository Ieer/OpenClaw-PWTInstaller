#!/bin/sh
set -eu

MAX_RETRIES="${MC_DB_MIGRATION_MAX_RETRIES:-30}"
SLEEP_SECONDS="${MC_DB_MIGRATION_RETRY_INTERVAL_SECONDS:-2}"

classify_migration_error() {
  lower_output="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"

  case "$lower_output" in
    *"password authentication failed"*|*"invalidpassworderror"*|*"authentication failed"*|*"no pg_hba.conf entry"*)
      printf '%s\n' "db-auth"
      ;;
    *"target database is not up to date"*|*"can't locate revision"*|*"multiple head"*|*"duplicate table"*|*"duplicate column"*|*"undefined table"*|*"syntax error"*)
      printf '%s\n' "migration-error"
      ;;
    *"connection refused"*|*"could not connect to server"*|*"connect call failed"*|*"database system is starting up"*|*"server closed the connection"*|*"connection is closed"*|*"timeout"*|*"timed out"*)
      printf '%s\n' "db-not-ready"
      ;;
    *"could not translate host name"*|*"name or service not known"*|*"temporary failure in name resolution"*|*"nodename nor servname"*)
      printf '%s\n' "db-host"
      ;;
    *)
      printf '%s\n' "unknown"
      ;;
  esac
}

should_retry_migration_error() {
  case "$1" in
    db-not-ready|db-host|unknown)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [ "${MC_ENTRYPOINT_CLASSIFY_ONLY:-0}" = "1" ]; then
  classify_migration_error "$(cat)"
  exit 0
fi

attempt=1
while [ "$attempt" -le "$MAX_RETRIES" ]; do
  migration_output_file="$(mktemp)"
  if alembic upgrade head >"$migration_output_file" 2>&1; then
    cat "$migration_output_file"
    rm -f "$migration_output_file"
    break
  fi

  migration_output="$(cat "$migration_output_file")"
  rm -f "$migration_output_file"
  if [ -n "$migration_output" ]; then
    printf '%s\n' "$migration_output" >&2
  fi

  migration_class="$(classify_migration_error "$migration_output")"
  echo "[mission-control-api] migration attempt ${attempt}/${MAX_RETRIES} failed (class=${migration_class})" >&2

  if ! should_retry_migration_error "$migration_class"; then
    echo "[mission-control-api] non-retryable migration failure (${migration_class}); check MC_DATABASE_URL and Alembic migration scripts" >&2
    exit 1
  fi

  if [ "$attempt" -eq "$MAX_RETRIES" ]; then
    echo "[mission-control-api] alembic migration failed after ${MAX_RETRIES} attempts (last_class=${migration_class})" >&2
    exit 1
  fi

  echo "[mission-control-api] retry migration in ${SLEEP_SECONDS}s..." >&2
  sleep "$SLEEP_SECONDS"
  attempt=$((attempt + 1))
done

exec uvicorn app.main:app --host 0.0.0.0 --port 9090
