#!/usr/bin/env bash
set -euo pipefail

# Bootstrap OpenClaw Panopticon local env, rotate gateway tokens, and restart the stack.
#
# - Creates missing local override env files from *.env.example
# - Generates strong random tokens (not printed)
# - Writes local override env files under panopticon/env/*.env (gitignored)
# - Updates panopticon/agent-homes/<agent>/openclaw.json gateway.auth.token
# - Regenerates the compose file and validates generated artifacts
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

echo "[1/7] Ensuring local env overrides exist"
if [[ -f "panopticon/.env.example" && ! -f "panopticon/.env" ]]; then
  cp "panopticon/.env.example" "panopticon/.env"
fi

for example in panopticon/env/*.env.example; do
  target="${example%.example}"
  if [[ ! -f "$target" ]]; then
    cp "$example" "$target"
  fi
done

echo "[2/7] Generating tokens + writing local env overrides (gitignored)"
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


def read_lines(path: Path) -> list[str]:
  if not path.exists():
    return []
  return path.read_text(encoding='utf-8').splitlines()


def write_lines(path: Path, lines: list[str]) -> None:
  content = '\n'.join(lines).rstrip('\n') + '\n'
  path.write_text(content, encoding='utf-8')


def upsert_env_value(path: Path, key: str, value: str) -> None:
  lines = read_lines(path)
  updated: list[str] = []
  found = False
  for raw_line in lines:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith('#') or '=' not in raw_line:
      updated.append(raw_line)
      continue
    current_key, _ = raw_line.split('=', 1)
    if current_key.strip() == key:
      updated.append(f'{key}={value}')
      found = True
    else:
      updated.append(raw_line)
  if not found:
    if updated and updated[-1] != '':
      updated.append('')
    updated.append(f'{key}={value}')
  write_lines(path, updated)


def load_env_value(path: Path, key: str) -> str:
  for raw_line in read_lines(path):
    stripped = raw_line.strip()
    if not stripped or stripped.startswith('#') or '=' not in raw_line:
      continue
    current_key, current_value = raw_line.split('=', 1)
    if current_key.strip() == key:
      return current_value.strip()
  return ''

# per-agent override env files (token updates only)
for slug, token in tokens.items():
  upsert_env_value(env_dir / f'{slug}.env', 'OPENCLAW_GATEWAY_TOKEN', token)

# mission-control-ui token map env (server-side injection path)
map_value = ','.join([f"{slug}={tokens[slug]}" for slug in slugs])
mission_control_env_path = env_dir / 'mission-control.env'
mission_control_auth_token = load_env_value(mission_control_env_path, 'MC_AUTH_TOKEN')
upsert_env_value(env_dir / 'mission-control-ui.env', 'MC_CHAT_HOST', '127.0.0.1')
upsert_env_value(env_dir / 'mission-control-ui.env', 'MC_CHAT_AGENT_TOKEN_MAP', map_value)
if mission_control_auth_token:
  upsert_env_value(env_dir / 'mission-control-ui.env', 'MISSION_CONTROL_AUTH_TOKEN', mission_control_auth_token)

# mission-control-gateway (nginx) per-agent auth env
for slug in slugs:
  upsert_env_value(env_dir / 'mission-control-gateway.env', f'TOKEN_{slug.upper()}', tokens[slug])

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

echo "[3/7] Regenerating compose artifacts"
python panopticon/tools/generate_panopticon.py --prune

echo "[4/7] Validating panopticon manifest, generated artifacts, and skills template"
python panopticon/tools/validate_panopticon.py
python panopticon/tools/validate_skills_template.py

echo "[5/7] Force-recreating services to load new env"
SERVICES=(mission-control-api mission-control-ui mission-control-gateway mc-heartbeat)
for agent in "${AGENTS[@]}"; do
  SERVICES+=("openclaw-$agent")
done

if docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | grep -qx "mission-control-agent-controller"; then
  SERVICES+=(mission-control-agent-controller)
fi

# Recreate API/UI/gateway and agents so env_file changes are applied.
docker compose -f "$COMPOSE_FILE" up -d --no-build --force-recreate "${SERVICES[@]}"

echo "[6/7] Waiting for gateways to become reachable"
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

echo "[7/7] Smoke checks"
# Check the unified entrypoint is alive.
for i in {1..10}; do
  code="$(curl -L -sS -o /dev/null -w '%{http_code}' http://localhost:18920 || true)"
  if [[ "$code" == "200" ]]; then
    echo "MC(18920)=200"
    break
  fi
  echo "MC(18920)=$code (retry $i/10)"
  sleep 1
done

for i in {1..20}; do
  code="$(curl -L -sS -o /dev/null -w '%{http_code}' http://localhost:18920/chat/nox/ || true)"
  if [[ "$code" == "200" ]]; then
    echo "chat_proxy(nox)=200"
    break
  fi
  echo "chat_proxy(nox)=$code (retry $i/20)"
  sleep 2
done

echo "Done. Tokens rotated and services restarted."
echo "Note: runtime tokens are stored only in panopticon/env/*.env (gitignored)."
