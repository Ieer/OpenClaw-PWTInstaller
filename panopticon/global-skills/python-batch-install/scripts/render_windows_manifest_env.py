from __future__ import annotations

import sys
from pathlib import Path

from manifest_common import load_manifest


def cmd_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "^": "^^",
        "&": "^&",
        "|": "^|",
        "<": "^<",
        ">": "^>",
        "%": "%%",
        '"': '^"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def emit(name: str, value: object) -> None:
    print(f'set "{name}={cmd_escape(value)}"')


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render_windows_manifest_env.py <manifest>", file=sys.stderr)
        return 2

    manifest_path = Path(sys.argv[1])
    if not manifest_path.is_file():
        print(f"Manifest file not found: {manifest_path}", file=sys.stderr)
        return 1

    data = load_manifest(manifest_path)
    workspace = data.get("workspace", {})
    windows = data.get("windows", {})
    verification = data.get("verification", {})
    envs = windows.get("envs", [])
    snippets = verification.get("python_snippets", [])

    emit("MANIFEST_WORKSPACE_DIR", workspace.get("root", ""))
    emit("MANIFEST_WINDOWS_BASE_PYTHON", windows.get("base_python", ""))
    emit("MANIFEST_WINDOWS_VENV_ROOT", windows.get("venv_root", ""))
    emit("MANIFEST_WINDOWS_INSTALL_SCRIPT", windows.get("install_script", ""))
    emit("MANIFEST_WINDOWS_REQUIREMENTS", windows.get("requirements", ""))
    emit("MANIFEST_WINDOWS_PACKAGE_DIR", windows.get("package_dir", ""))
    emit("MANIFEST_ENV_NAMES", " ".join(env.get("name", "") for env in envs if env.get("name")))
    emit("MANIFEST_ENV_COUNT", max(len(envs) - 1, -1))
    emit("MANIFEST_VERIFY_PIP_SHOW", " ".join(verification.get("pip_show", [])))
    emit("MANIFEST_SNIPPET_COUNT", max(len(snippets) - 1, -1))

    for index, env in enumerate(envs):
        emit(f"MANIFEST_ENV_{index}_NAME", env.get("name", ""))
        emit(f"MANIFEST_ENV_{index}_VERIFY_IMPORTS", " ".join(env.get("verify_imports", [])))

    for index, snippet in enumerate(snippets):
        emit(f"MANIFEST_SNIPPET_{index}", snippet)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())