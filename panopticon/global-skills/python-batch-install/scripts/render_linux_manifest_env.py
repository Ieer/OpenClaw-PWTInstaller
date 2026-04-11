from __future__ import annotations

import shlex
import sys
from pathlib import Path

from manifest_common import load_manifest


def shell_array(name: str, values: list[str]) -> str:
    joined = " ".join(shlex.quote(str(value)) for value in values)
    return f"{name}=({joined})"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render_linux_manifest_env.py <manifest>", file=sys.stderr)
        return 2

    manifest_path = Path(sys.argv[1])
    if not manifest_path.is_file():
        print(f"Manifest file not found: {manifest_path}", file=sys.stderr)
        return 1

    data = load_manifest(manifest_path)
    workspace = data.get("workspace", {})
    linux = data.get("linux", {})
    verification = data.get("verification", {})
    envs = linux.get("envs", [])

    env_names: list[str] = []
    env_verify_imports: list[str] = []
    for env in envs:
        env_names.append(env.get("name", ""))
        env_verify_imports.append(",".join(env.get("verify_imports", [])))

    print(f"MANIFEST_WORKSPACE_DIR={shlex.quote(workspace.get('root', ''))}")
    print(f"MANIFEST_LINUX_BASE_PYTHON={shlex.quote(linux.get('base_python', ''))}")
    print(f"MANIFEST_LINUX_VENV_ROOT={shlex.quote(linux.get('venv_root', ''))}")
    print(f"MANIFEST_LINUX_INSTALL_SCRIPT={shlex.quote(linux.get('install_script', ''))}")
    print(f"MANIFEST_LINUX_REQUIREMENTS={shlex.quote(linux.get('requirements', ''))}")
    print(f"MANIFEST_LINUX_PACKAGE_DIR={shlex.quote(linux.get('package_dir', ''))}")
    print(shell_array("MANIFEST_ENV_NAMES", env_names))
    print(shell_array("MANIFEST_ENV_VERIFY_IMPORTS", env_verify_imports))
    print(shell_array("MANIFEST_PIP_SHOW", verification.get("pip_show", [])))
    print(shell_array("MANIFEST_PYTHON_SNIPPETS", verification.get("python_snippets", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())