from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".release-state"
RELEASE_PATH = ROOT / "openclaw-release.yaml"
MANIFEST_PATH = ROOT / "panopticon" / "agents.manifest.yaml"
COMPOSE_FILE = ROOT / "panopticon" / "docker-compose.panopticon.yml"
PYTHON = ROOT / ".venv" / "bin" / "python"


def python_exe() -> str:
    return str(PYTHON if PYTHON.exists() else Path(sys.executable))


def load_manifest_agents() -> list[str]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("agents.manifest.yaml must be a mapping")
    agents = data.get("agents")
    if not isinstance(agents, list):
        raise ValueError("manifest agents must be a list")
    out: list[str] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        if not item.get("enabled", True):
            continue
        slug = str(item.get("slug") or "").strip()
        if slug:
            out.append(slug)
    return out


def run_step(label: str, cmd: list[str]) -> None:
    print(f"==> {label}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def snapshot_release(selected_agents: list[str], include_mission_control: bool) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release_snapshot = STATE_DIR / f"release-{stamp}.yaml"
    metadata_path = STATE_DIR / "last-rollout.json"
    shutil.copy2(RELEASE_PATH, release_snapshot)
    metadata = {
        "created_at": stamp,
        "release_snapshot": str(release_snapshot.relative_to(ROOT)),
        "selected_agents": selected_agents,
        "include_mission_control": include_mission_control,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return release_snapshot


def build_services(selected_agents: list[str], include_mission_control: bool) -> list[str]:
    services = [f"openclaw-{slug}" for slug in selected_agents]
    if include_mission_control:
        services = ["mission-control-api", "mission-control-ui", "mission-control-gateway", *services]
    return services


def main() -> int:
    parser = argparse.ArgumentParser(description="Gray rollout OpenClaw release changes through Panopticon")
    parser.add_argument("agents", nargs="*", help="Agent slugs to rollout; default is all enabled agents")
    parser.add_argument("--skip-prepare", action="store_true", help="Skip prepare_release_upgrade checks before rollout")
    parser.add_argument("--skip-build", action="store_true", help="Skip docker compose build step")
    parser.add_argument("--no-mission-control", action="store_true", help="Do not recreate mission-control services")
    parser.add_argument("--smoke-base-url", default="http://localhost:18920", help="Gateway base URL for post-rollout smoke test")
    args = parser.parse_args()

    selected_agents = args.agents or load_manifest_agents()
    include_mission_control = not args.no_mission_control

    snapshot = snapshot_release(selected_agents, include_mission_control)
    print(f"Saved rollback snapshot: {snapshot.relative_to(ROOT)}")

    if not args.skip_prepare:
        run_step(
            "Prepare release upgrade",
            [python_exe(), str(ROOT / "tools" / "prepare_release_upgrade.py"), "--skip-smoke"],
        )

    services = build_services(selected_agents, include_mission_control)
    compose_base = ["docker", "compose", "-f", str(COMPOSE_FILE)]

    if not args.skip_build:
        run_step("Build selected services", [*compose_base, "build", *services])

    run_step("Recreate selected services", [*compose_base, "up", "-d", "--force-recreate", *services])

    smoke_cmd = [python_exe(), str(ROOT / "panopticon" / "tools" / "smoke_chat_proxy.py"), "--base-url", args.smoke_base_url, *selected_agents]
    run_step("Post-rollout smoke", smoke_cmd)

    print("Rollout completed.")
    print("If you need to undo this rollout, run: python tools/rollback_release_upgrade.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
