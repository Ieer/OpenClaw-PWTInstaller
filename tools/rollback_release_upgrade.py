from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".release-state"
RELEASE_PATH = ROOT / "openclaw-release.yaml"
COMPOSE_FILE = ROOT / "panopticon" / "docker-compose.panopticon.yml"
PYTHON = ROOT / ".venv" / "bin" / "python"


def python_exe() -> str:
    return str(PYTHON if PYTHON.exists() else Path(sys.executable))


def load_last_rollout() -> dict:
    metadata_path = STATE_DIR / "last-rollout.json"
    if not metadata_path.exists():
        raise FileNotFoundError("no last-rollout.json found under .release-state")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def run_step(label: str, cmd: list[str]) -> None:
    print(f"==> {label}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback the last OpenClaw release rollout")
    parser.add_argument("--snapshot", help="Optional explicit snapshot path relative to repo root or absolute path")
    parser.add_argument("--smoke-base-url", default="http://localhost:18920", help="Gateway base URL for post-rollback smoke test")
    args = parser.parse_args()

    metadata = load_last_rollout()
    snapshot_arg = args.snapshot or metadata.get("release_snapshot")
    if not snapshot_arg:
        raise SystemExit("no release snapshot available")

    snapshot = Path(snapshot_arg)
    if not snapshot.is_absolute():
        snapshot = ROOT / snapshot
    if not snapshot.exists():
        raise FileNotFoundError(f"snapshot not found: {snapshot}")

    shutil.copy2(snapshot, RELEASE_PATH)
    print(f"Restored release contract from {snapshot.relative_to(ROOT)}")

    run_step("Prepare restored release", [python_exe(), str(ROOT / "tools" / "prepare_release_upgrade.py"), "--skip-smoke"])

    selected_agents = [str(x) for x in metadata.get("selected_agents", []) if str(x).strip()]
    include_mission_control = bool(metadata.get("include_mission_control", True))
    services = [f"openclaw-{slug}" for slug in selected_agents]
    if include_mission_control:
        services = ["mission-control-api", "mission-control-ui", "mission-control-gateway", *services]

    compose_base = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    run_step("Recreate rollback services", [*compose_base, "up", "-d", "--force-recreate", *services])

    smoke_cmd = [python_exe(), str(ROOT / "panopticon" / "tools" / "smoke_chat_proxy.py"), "--base-url", args.smoke_base_url, *selected_agents]
    run_step("Post-rollback smoke", smoke_cmd)

    print("Rollback completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
