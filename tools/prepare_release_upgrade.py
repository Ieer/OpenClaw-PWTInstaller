from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"


def _python_cmd(script: Path, *extra: str) -> list[str]:
    python_exe = str(PYTHON if PYTHON.exists() else Path(sys.executable))
    return [python_exe, str(script), *extra]


def run_step(label: str, cmd: list[str]) -> None:
    print(f"==> {label}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify an OpenClaw release upgrade")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip /chat smoke verification")
    parser.add_argument("--smoke-base-url", default="http://localhost:18920", help="Mission Control gateway base URL")
    parser.add_argument("agents", nargs="*", help="Optional agent slug list for smoke test")
    args = parser.parse_args()

    run_step("Sync release contract defaults", _python_cmd(ROOT / "tools" / "sync_openclaw_release.py"))
    run_step("Generate Panopticon artifacts", _python_cmd(ROOT / "panopticon" / "tools" / "generate_panopticon.py"))
    run_step("Validate Panopticon and release alignment", _python_cmd(ROOT / "panopticon" / "tools" / "validate_panopticon.py"))

    py_compile_cmd = [
        str(PYTHON if PYTHON.exists() else Path(sys.executable)),
        "-m",
        "py_compile",
        "mission_control_api/app/config.py",
        "mission_control_api/app/main.py",
        "MissionControl/app.py",
        "panopticon/tools/smoke_chat_proxy.py",
    ]
    run_step("Compile Python entrypoints", py_compile_cmd)

    if not args.skip_smoke:
        smoke_cmd = _python_cmd(
            ROOT / "panopticon" / "tools" / "smoke_chat_proxy.py",
            "--base-url",
            args.smoke_base_url,
            *args.agents,
        )
        run_step("Run chat smoke tests", smoke_cmd)

    print("Release upgrade preparation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
