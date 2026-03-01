#!/usr/bin/env bash
set -euo pipefail

# Rotate OpenClaw gateway tokens for 8 agents and restart panopticon stack.
#
# - Generates strong random tokens (not printed)
# - Writes local override env files under panopticon/env/*.env (gitignored)
# - Updates panopticon/agent-homes/<agent>/openclaw.json gateway.auth.token
# - Force-recreates relevant containers so new env is loaded
# - Runs endpoint checks

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/panopticon/docker-compose.panopticon.yml"

AGENTS=(nox metrics email growth trades health writing personal)

cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose not available" >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "python not found" >&2
  exit 1
fi

echo "[1/4] Generating tokens + writing local env overrides (gitignored)"
python - <<'PY'
import json
import secrets
from pathlib import Path

repo = Path('.').resolve()
env_dir = repo / 'panopticon' / 'env'
agent_homes = repo / 'panopticon' / 'agent-homes'
slugs = ['nox','metrics','email','growth','trades','health','writing','personal']

env_dir.mkdir(parents=True, exist_ok=True)

tokens = {slug: secrets.token_urlsafe(32) for slug in slugs}

# per-agent override env files (token only)
for slug, token in tokens.items():
    (env_dir / f'{slug}.env').write_text(f'OPENCLAW_GATEWAY_TOKEN={token}\n', encoding='utf-8')

# mission-control-ui token map env (server-side injection path)
map_value = ','.join([f"{slug}={tokens[slug]}" for slug in slugs])
(env_dir / 'mission-control-ui.env').write_text(
    '\n'.join([
        '# Mission Control Dash UI (local overrides; do not commit)',
        'MISSION_CONTROL_CHAT_AUTH_SCHEME=Bearer',
        'MISSION_CONTROL_CHAT_CONTAINER_GATEWAY_PORT=26216',
        'MISSION_CONTROL_CHAT_HOST=127.0.0.1',
        f'MISSION_CONTROL_CHAT_AGENT_TOKEN_MAP={map_value}',
        ''
    ]),
    encoding='utf-8'
)

# mission-control-gateway (nginx) per-agent auth env
lines = ['# nginx chat gateway token env (local; do not commit)']
for slug in slugs:
    lines.append(f'TOKEN_{slug.upper()}={tokens[slug]}')
lines.append('')
(env_dir / 'mission-control-gateway.env').write_text('\n'.join(lines), encoding='utf-8')

# patch agent-homes openclaw.json token
for slug, token in tokens.items():
    p = agent_homes / slug / 'openclaw.json'
    if not p.exists():
        raise SystemExit(f'missing {p}')
    data = json.loads(p.read_text(encoding='utf-8'))
    data.setdefault('gateway', {})
    data['gateway'].setdefault('auth', {})
    data['gateway']['auth']['token'] = token
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print('ok')
PY

echo "[2/4] Force-recreating services to load new env"
# Recreate API/UI/gateway and agents so env_file changes are applied.
docker compose -f "$COMPOSE_FILE" up -d --no-build --force-recreate \
  mission-control-api mission-control-ui mission-control-gateway \
  openclaw-nox openclaw-metrics openclaw-email openclaw-growth openclaw-trades openclaw-health openclaw-writing openclaw-personal

echo "[3/4] Waiting for gateways to become reachable"
# Gateways can take a bit to come up after token reload.
for i in {1..30}; do
  if bash panopticon/tools/check_agent_endpoints.sh >/dev/null 2>&1; then
    echo "Gateways OK"
    break
  fi
  echo "...waiting ($i/30)"
  sleep 3
  if [[ $i -eq 30 ]]; then
    echo "Gateway checks still failing; showing full output:" >&2
    bash panopticon/tools/check_agent_endpoints.sh || true
  fi
done

echo "[4/4] Smoke checks"
# Check the unified entrypoint is alive.
for i in {1..10}; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18920 || true)"
  if [[ "$code" == "200" ]]; then
    echo "MC(18920)=200"
    break
  fi
  echo "MC(18920)=$code (retry $i/10)"
  sleep 1
done

for i in {1..20}; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18920/chat/nox/ || true)"
  if [[ "$code" == "200" ]]; then
    echo "chat_proxy(nox)=200"
    break
  fi
  echo "chat_proxy(nox)=$code (retry $i/20)"
  sleep 2
done

echo "Done. Tokens rotated and services restarted."
echo "Note: token files are under panopticon/env/*.env (gitignored)."
