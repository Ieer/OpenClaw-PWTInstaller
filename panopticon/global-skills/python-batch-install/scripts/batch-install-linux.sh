#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_MANIFEST="$SCRIPT_DIR/../assets/environment-manifest.template.yaml"
MANIFEST_FILE="${MANIFEST_FILE:-$DEFAULT_MANIFEST}"
MANIFEST_PYTHON="${MANIFEST_PYTHON:-/usr/bin/python3}"
MANIFEST_HELPER="$SCRIPT_DIR/render_linux_manifest_env.py"
DRY_RUN="${DRY_RUN:-0}"

if [[ ! -f "$MANIFEST_FILE" ]]; then
  printf '[ERROR] Manifest file not found: %s\n' "$MANIFEST_FILE" >&2
  exit 1
fi

if ! command -v "$MANIFEST_PYTHON" >/dev/null 2>&1; then
  printf '[ERROR] Manifest parser Python not found: %s\n' "$MANIFEST_PYTHON" >&2
  exit 1
fi

if [[ ! -f "$MANIFEST_HELPER" ]]; then
  printf '[ERROR] Manifest helper not found: %s\n' "$MANIFEST_HELPER" >&2
  exit 1
fi

eval "$("$MANIFEST_PYTHON" "$MANIFEST_HELPER" "$MANIFEST_FILE")"

WORKSPACE_DIR="${WORKSPACE_DIR:-$MANIFEST_WORKSPACE_DIR}"
VENV_ROOT="${VENV_ROOT:-$MANIFEST_LINUX_VENV_ROOT}"
BASE_PYTHON="${BASE_PYTHON:-$MANIFEST_LINUX_BASE_PYTHON}"
PACKAGE_DIR="${PACKAGE_DIR:-$MANIFEST_LINUX_PACKAGE_DIR}"
REQ_FILE="${REQ_FILE:-$MANIFEST_LINUX_REQUIREMENTS}"
INSTALL_SCRIPT="${INSTALL_SCRIPT:-$MANIFEST_LINUX_INSTALL_SCRIPT}"

if [[ -n "${ENV_NAMES:-}" ]]; then
  IFS=' ' read -r -a ENV_NAMES <<< "$ENV_NAMES"
else
  ENV_NAMES=("${MANIFEST_ENV_NAMES[@]}")
fi

ENV_VERIFY_IMPORTS=("${MANIFEST_ENV_VERIFY_IMPORTS[@]}")
VERIFY_PIP_SHOW=("${MANIFEST_PIP_SHOW[@]}")
VERIFY_SNIPPETS=("${MANIFEST_PYTHON_SNIPPETS[@]}")

SUCCESS_ENVS=()
FAILED_ENVS=()

log() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

fail_env() {
  local env_name="$1"
  local reason="$2"
  FAILED_ENVS+=("$env_name: $reason")
}

print_plan() {
  printf '\nDry-run plan\n'
  printf 'Manifest: %s\n' "$MANIFEST_FILE"
  printf 'Workspace: %s\n' "$WORKSPACE_DIR"
  printf 'Base Python: %s\n' "$BASE_PYTHON"
  printf 'Install script: %s\n' "$INSTALL_SCRIPT"
  printf 'Wheel dir: %s\n' "$PACKAGE_DIR"
  printf 'Requirements: %s\n' "$REQ_FILE"
  printf 'Venv root: %s\n' "$VENV_ROOT"
  printf 'Pip show checks: %s\n' "${VERIFY_PIP_SHOW[*]:-}"

  for env_index in "${!ENV_NAMES[@]}"; do
    local env_name="${ENV_NAMES[$env_index]}"
    local env_dir="$VENV_ROOT/$env_name"
    local verify_imports_csv="${ENV_VERIFY_IMPORTS[$env_index]:-}"
    printf '\nPlanned environment: %s\n' "$env_name"
    printf '  venv: %s\n' "$env_dir"
    printf '  imports: %s\n' "${verify_imports_csv:-<none>}"
  done

  if (( ${#VERIFY_SNIPPETS[@]} > 0 )); then
    printf '\nPython snippet checks\n'
    for snippet in "${VERIFY_SNIPPETS[@]}"; do
      printf '  %s\n' "$snippet"
    done
  fi
}

if [[ ! -x "$BASE_PYTHON" && ! -f "$BASE_PYTHON" ]]; then
  printf '[ERROR] Base Python not found: %s\n' "$BASE_PYTHON" >&2
  exit 1
fi

if [[ ! -f "$REQ_FILE" ]]; then
  printf '[ERROR] Requirements file not found: %s\n' "$REQ_FILE" >&2
  exit 1
fi

if [[ ! -d "$PACKAGE_DIR" ]]; then
  printf '[ERROR] Package directory not found: %s\n' "$PACKAGE_DIR" >&2
  exit 1
fi

if [[ ! -x "$INSTALL_SCRIPT" ]]; then
  printf '[ERROR] Install script not executable: %s\n' "$INSTALL_SCRIPT" >&2
  exit 1
fi

if (( ${#ENV_NAMES[@]} == 0 )); then
  printf '[ERROR] No Linux environments found in manifest: %s\n' "$MANIFEST_FILE" >&2
  exit 1
fi

if [[ "$DRY_RUN" == "1" ]]; then
  print_plan
  exit 0
fi

mkdir -p "$VENV_ROOT"

for env_index in "${!ENV_NAMES[@]}"; do
  env_name="${ENV_NAMES[$env_index]}"
  env_dir="$VENV_ROOT/$env_name"
  python_bin="$env_dir/bin/python"
  verify_imports_csv="${ENV_VERIFY_IMPORTS[$env_index]:-}"

  log "Preparing venv: $env_dir"
  rm -rf "$env_dir"

  if ! "$BASE_PYTHON" -m venv "$env_dir"; then
    fail_env "$env_name" "venv creation failed"
    continue
  fi

  log "Installing requirements into: $env_name"
  if ! PYTHON_BIN="$python_bin" PACKAGE_DIR="$PACKAGE_DIR" REQ_FILE="$REQ_FILE" "$INSTALL_SCRIPT"; then
    fail_env "$env_name" "offline installation failed"
    continue
  fi

  log "Verifying key packages in: $env_name"
  if (( ${#VERIFY_PIP_SHOW[@]} > 0 )) && ! "$python_bin" -m pip show "${VERIFY_PIP_SHOW[@]}" >/dev/null; then
    fail_env "$env_name" "pip show verification failed"
    continue
  fi

  if [[ -n "$verify_imports_csv" ]]; then
    IFS=',' read -r -a verify_imports <<< "$verify_imports_csv"
    for module_name in "${verify_imports[@]}"; do
      [[ -z "$module_name" ]] && continue
      if ! "$python_bin" -c "import ${module_name}" >/dev/null 2>&1; then
        fail_env "$env_name" "module import verification failed: ${module_name}"
        continue 2
      fi
    done
  fi

  for snippet in "${VERIFY_SNIPPETS[@]}"; do
    [[ -z "$snippet" ]] && continue
    if ! "$python_bin" -c "$snippet"; then
      fail_env "$env_name" "python snippet verification failed"
      continue 2
    fi
  done

  SUCCESS_ENVS+=("$env_name")
done

printf '\nBatch install summary\n'
printf 'Manifest: %s\n' "$MANIFEST_FILE"
printf 'Workspace: %s\n' "$WORKSPACE_DIR"
printf 'Wheel dir: %s\n' "$PACKAGE_DIR"
printf 'Requirements: %s\n' "$REQ_FILE"
printf 'Venv root: %s\n' "$VENV_ROOT"

printf '\nSuccessful environments (%s)\n' "${#SUCCESS_ENVS[@]}"
for env_name in "${SUCCESS_ENVS[@]}"; do
  printf '  - %s\n' "$env_name"
done

printf '\nFailed environments (%s)\n' "${#FAILED_ENVS[@]}"
for failure in "${FAILED_ENVS[@]}"; do
  printf '  - %s\n' "$failure"
done

if (( ${#FAILED_ENVS[@]} > 0 )); then
  exit 1
fi