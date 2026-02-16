from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "agents.manifest.yaml"
COMPOSE_PATH = ROOT / "docker-compose.panopticon.yml"
ENV_DIR = ROOT / "env"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a mapping")
    return data


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []

    required_top = ["version", "mission_control", "agent_runtime", "agents"]
    for key in required_top:
        if key not in manifest:
            errors.append(f"missing top-level field: {key}")

    mission_control = manifest.get("mission_control", {})
    for key in ["api_port", "ui_port"]:
        if key not in mission_control:
            errors.append(f"missing mission_control.{key}")
        elif not isinstance(mission_control[key], int):
            errors.append(f"mission_control.{key} must be int")

    runtime = manifest.get("agent_runtime", {})
    for key in ["cnim_build_context", "cnim_dockerfile", "cnim_image", "container_gateway_port", "container_bridge_port"]:
        if key not in runtime:
            errors.append(f"missing agent_runtime.{key}")

    agents = manifest.get("agents", [])
    if not isinstance(agents, list) or not agents:
        errors.append("agents must be a non-empty list")
        return errors

    seen_slugs: set[str] = set()
    used_ports: dict[int, str] = {}

    for index, agent in enumerate(agents):
        prefix = f"agents[{index}]"
        slug = agent.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            errors.append(f"{prefix}.slug invalid (use lowercase letters/numbers/hyphen)")
            continue

        if slug in seen_slugs:
            errors.append(f"duplicate slug: {slug}")
        seen_slugs.add(slug)

        if "role" not in agent:
            errors.append(f"{prefix}.role is required")

        enabled = bool(agent.get("enabled", True))
        if not enabled:
            continue

        for key in ["gateway_host_port", "bridge_host_port"]:
            value = agent.get(key)
            if not isinstance(value, int):
                errors.append(f"{prefix}.{key} must be int")
                continue
            if value < 1024 or value > 65535:
                errors.append(f"{prefix}.{key} out of range: {value}")
                continue
            if value in used_ports:
                errors.append(f"port conflict: {value} used by {used_ports[value]} and {slug}")
            else:
                used_ports[value] = slug

        if not agent.get("gateway_token"):
            errors.append(f"{prefix}.gateway_token is required for enabled agent")

    return errors


def validate_generated_files(manifest: dict) -> list[str]:
    errors: list[str] = []

    if not COMPOSE_PATH.exists():
        errors.append(f"missing generated compose file: {COMPOSE_PATH}")

    enabled_agents = [a for a in manifest.get("agents", []) if a.get("enabled", True)]
    for agent in enabled_agents:
        slug = agent["slug"]
        env_path = ENV_DIR / f"{slug}.env.example"
        if not env_path.exists():
            errors.append(f"missing generated env file: {env_path}")

    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate panopticon agents manifest and generated artifacts"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="Path to agents.manifest.yaml",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    errors = validate_manifest(manifest)
    errors.extend(validate_generated_files(manifest))

    if errors:
        print("Validation failed:")
        for item in errors:
            print(f"- {item}")
        raise SystemExit(1)

    print("Validation passed.")
