#!/usr/bin/env bash

knowledge_repo_root() {
  local script_dir="$1"
  (cd "$script_dir/.." && pwd)
}

knowledge_trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s\n' "$value"
}

knowledge_env_file_value() {
  local file="$1"
  local key="$2"
  local line current_key current_value

  [[ -f "$file" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    current_value="$(knowledge_trim "$line")"
    [[ -z "$current_value" || "$current_value" == \#* || "$current_value" != *=* ]] && continue

    current_key="$(knowledge_trim "${current_value%%=*}")"
    if [[ "$current_key" == "$key" ]]; then
      knowledge_trim "${current_value#*=}"
      return 0
    fi
  done < "$file"
}

knowledge_sources_root() {
  local root_dir="$1"
  local raw_path="${USB_KNOWLEDGE_ROOT:-${PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH:-}}"

  if [[ -z "$raw_path" ]]; then
    raw_path="$(knowledge_env_file_value "$root_dir/panopticon/.env" PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH)"
  fi

  if [[ -z "$raw_path" ]]; then
    raw_path="$root_dir/panopticon/mission-control/knowledge-sources"
  elif [[ "$raw_path" != /* ]]; then
    raw_path="$root_dir/panopticon/$raw_path"
  fi

  printf '%s\n' "$raw_path"
}

knowledge_python_bin() {
  local root_dir="$1"

  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi

  if [[ -x "$root_dir/.venv/bin/python" ]]; then
    printf '%s\n' "$root_dir/.venv/bin/python"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  echo "python3 or python is required" >&2
  return 1
}
