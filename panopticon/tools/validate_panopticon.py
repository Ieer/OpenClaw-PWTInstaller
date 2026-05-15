from __future__ import annotations

import argparse
import json
import os
import re
import socket
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "agents.manifest.yaml"
COMPOSE_PATH = ROOT / "docker-compose.panopticon.yml"
ENV_DIR = ROOT / "env"
PANOPTICON_DOTENV_PATH = ROOT / ".env"
RELEASE_PATH = ROOT.parent / "openclaw-release.yaml"

REQUIRED_STATIC_ENV_EXAMPLES = {
    "mission-control.env.example",
    "mission-control-ui.env.example",
    "mission-control-gateway.env.example",
    "mission-control-voice-bridge.env.example",
}

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER_VALUE_RE = re.compile(r"^(CHANGE_ME|TODO|REPLACE_ME|YOUR_TOKEN)(?:[_-].*)?$", re.IGNORECASE)
TRUE_VALUE_RE = re.compile(r"^(1|true|yes|on)$", re.IGNORECASE)


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a mapping")
    return data


def load_release(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("openclaw-release.yaml must be a mapping")
    return data


def _is_placeholder_value(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return bool(PLACEHOLDER_VALUE_RE.match(text))


def _is_true_value(value: object) -> bool:
    return bool(TRUE_VALUE_RE.match(str(value or "").strip()))


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_panopticon_environment() -> dict[str, str]:
    values = _load_env_file(PANOPTICON_DOTENV_PATH)
    for key, value in os.environ.items():
        if key.startswith("PANOPTICON_"):
            values[key] = value
    return values


def _resolve_panopticon_path(raw_value: str, *, base_dir: Path = ROOT) -> Path:
    raw = raw_value.strip()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve(strict=False)


def _host_port_accepts_connections(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _load_agent_runtime_env(slug: str) -> tuple[dict[str, str], bool]:
    example_values = _load_env_file(ENV_DIR / f"{slug}.env.example")
    local_env_path = ENV_DIR / f"{slug}.env"
    local_values = _load_env_file(local_env_path)
    merged = dict(example_values)
    merged.update(local_values)
    return merged, local_env_path.exists()


def _load_json_mapping(path: Path) -> tuple[dict[str, object] | None, str | None]:
    if not path.exists() or not path.is_file():
        return None, None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: line {exc.lineno} column {exc.colno}"

    if not isinstance(payload, dict):
        return None, f"{path} must be a JSON object"

    return payload, None


def _parse_token_map(value: str) -> tuple[dict[str, str], list[str]]:
    token_map: dict[str, str] = {}
    parse_errors: list[str] = []

    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if "=" not in item:
            parse_errors.append(item)
            continue
        key, token = item.split("=", 1)
        token_map[key.strip()] = token.strip()

    return token_map, parse_errors


def validate_runtime_consistency(manifest: dict) -> list[str]:
    errors: list[str] = []
    enabled_agents = [agent for agent in manifest.get("agents", []) if agent.get("enabled", True)]
    agent_tokens: dict[str, str] = {}

    for agent in enabled_agents:
        slug = str(agent.get("slug") or "").strip()
        if not slug:
            continue

        local_env_path = ENV_DIR / f"{slug}.env"
        if not local_env_path.exists():
            continue

        merged_env, _ = _load_agent_runtime_env(slug)
        required_keys = ("MODEL_ID", "BASE_URL", "API_KEY", "OPENCLAW_GATEWAY_TOKEN")
        required_errors = 0
        for key in required_keys:
            value = str(merged_env.get(key) or "").strip()
            if _is_placeholder_value(value):
                errors.append(f"panopticon/env/{slug}.env must set {key} to a non-placeholder value")
                required_errors += 1

        token = str(merged_env.get("OPENCLAW_GATEWAY_TOKEN") or "").strip()
        if required_errors > 0:
            continue
        if token:
            agent_tokens[slug] = token

        agent_home_path = ROOT / "agent-homes" / slug / "openclaw.json"
        json_payload, json_error = _load_json_mapping(agent_home_path)
        if json_error:
            errors.append(json_error)
            continue
        if json_payload is None:
            errors.append(f"missing runtime config: {agent_home_path}")
            continue

        gateway = json_payload.get("gateway")
        if not isinstance(gateway, dict):
            errors.append(f"{agent_home_path} must contain gateway.auth.token")
            continue

        auth = gateway.get("auth")
        if not isinstance(auth, dict):
            errors.append(f"{agent_home_path} must contain gateway.auth.token")
            continue

        json_token = str(auth.get("token") or "").strip()
        if json_token != token:
            errors.append(
                f"drift: {agent_home_path} gateway.auth.token does not match panopticon/env/{slug}.env OPENCLAW_GATEWAY_TOKEN"
            )

    gateway_env_path = ENV_DIR / "mission-control-gateway.env"
    if gateway_env_path.exists():
        gateway_env = _load_env_file(ENV_DIR / "mission-control-gateway.env.example")
        gateway_env.update(_load_env_file(gateway_env_path))
        for slug, token in agent_tokens.items():
            env_key = f"TOKEN_{slug.upper()}"
            gateway_token = str(gateway_env.get(env_key) or "").strip()
            if _is_placeholder_value(gateway_token):
                errors.append(
                    f"panopticon/env/mission-control-gateway.env must set {env_key} to the token from panopticon/env/{slug}.env"
                )
            elif gateway_token != token:
                errors.append(
                    f"drift: panopticon/env/mission-control-gateway.env {env_key} does not match panopticon/env/{slug}.env OPENCLAW_GATEWAY_TOKEN"
                )

    ui_env_path = ENV_DIR / "mission-control-ui.env"
    if ui_env_path.exists():
        ui_env = _load_env_file(ENV_DIR / "mission-control-ui.env.example")
        ui_env.update(_load_env_file(ui_env_path))

        token_map_value = str(ui_env.get("MC_CHAT_AGENT_TOKEN_MAP") or "").strip()
        if not token_map_value:
            errors.append(
                "panopticon/env/mission-control-ui.env must set MC_CHAT_AGENT_TOKEN_MAP to the agent token map generated by rotate_gateway_tokens.sh"
            )
        else:
            parsed_map, parse_errors = _parse_token_map(token_map_value)
            for item in parse_errors:
                errors.append(
                    f"panopticon/env/mission-control-ui.env MC_CHAT_AGENT_TOKEN_MAP contains an invalid entry: {item}"
                )

            for slug, token in agent_tokens.items():
                mapped_token = parsed_map.get(slug)
                if mapped_token is None:
                    errors.append(
                        f"panopticon/env/mission-control-ui.env MC_CHAT_AGENT_TOKEN_MAP is missing the token for agent {slug}"
                    )
                elif mapped_token != token:
                    errors.append(
                        f"drift: panopticon/env/mission-control-ui.env MC_CHAT_AGENT_TOKEN_MAP entry for {slug} does not match panopticon/env/{slug}.env OPENCLAW_GATEWAY_TOKEN"
                    )

        api_auth_token = str(ui_env.get("MISSION_CONTROL_AUTH_TOKEN") or "").strip()
        api_env = _load_env_file(ENV_DIR / "mission-control.env.example")
        api_env.update(_load_env_file(ENV_DIR / "mission-control.env"))
        mission_control_auth = str(api_env.get("MC_AUTH_TOKEN") or "").strip()
        if mission_control_auth and _is_placeholder_value(mission_control_auth):
            errors.append("panopticon/env/mission-control.env must set MC_AUTH_TOKEN to a non-placeholder value")
        if api_auth_token and _is_placeholder_value(api_auth_token):
            errors.append("panopticon/env/mission-control-ui.env must set MISSION_CONTROL_AUTH_TOKEN to a non-placeholder value")
        if mission_control_auth != api_auth_token:
            if mission_control_auth and not api_auth_token:
                errors.append(
                    "drift: panopticon/env/mission-control.env MC_AUTH_TOKEN is set, but panopticon/env/mission-control-ui.env MISSION_CONTROL_AUTH_TOKEN is empty"
                )
            elif api_auth_token and not mission_control_auth:
                errors.append(
                    "drift: panopticon/env/mission-control-ui.env MISSION_CONTROL_AUTH_TOKEN is set, but panopticon/env/mission-control.env MC_AUTH_TOKEN is empty"
                )
            else:
                errors.append(
                    "drift: panopticon/env/mission-control-ui.env MISSION_CONTROL_AUTH_TOKEN must match panopticon/env/mission-control.env MC_AUTH_TOKEN"
                )

    return errors


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
    if "agent_controller_enabled" in mission_control and not isinstance(mission_control["agent_controller_enabled"], bool):
        errors.append("mission_control.agent_controller_enabled must be bool")

    runtime = manifest.get("agent_runtime", {})
    for key in ["cnim_build_context", "cnim_dockerfile", "cnim_image", "container_gateway_port", "container_bridge_port"]:
        if key not in runtime:
            errors.append(f"missing agent_runtime.{key}")
    if "cnim_openclaw_version" in runtime and not isinstance(runtime["cnim_openclaw_version"], (str, int, float)):
        errors.append("agent_runtime.cnim_openclaw_version must be string-like")
    if "gateway_auth_mode" in runtime and not isinstance(runtime["gateway_auth_mode"], str):
        errors.append("agent_runtime.gateway_auth_mode must be string")
    if "control_ui_disable_device_auth" in runtime and not isinstance(runtime["control_ui_disable_device_auth"], bool):
        errors.append("agent_runtime.control_ui_disable_device_auth must be bool")

    agents = manifest.get("agents", [])
    if not isinstance(agents, list) or not agents:
        errors.append("agents must be a non-empty list")
        return errors

    seen_slugs: set[str] = set()
    used_ports: dict[int, str] = {}
    gateway_auth_mode = str(runtime.get("gateway_auth_mode") or "token").strip().lower() or "token"

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

        manifest_token = str(agent.get("gateway_token") or "").strip()
        if not manifest_token:
            errors.append(f"{prefix}.gateway_token is required for enabled agent")
        elif gateway_auth_mode == "token":
            runtime_env, has_local_env = _load_agent_runtime_env(slug)
            runtime_token = str(runtime_env.get("OPENCLAW_GATEWAY_TOKEN", manifest_token) or "").strip()
            if has_local_env and _is_placeholder_value(runtime_token):
                errors.append(
                    f"panopticon/env/{slug}.env must set OPENCLAW_GATEWAY_TOKEN to a non-placeholder value when present"
                )

    return errors


def validate_controller_security(manifest: dict) -> list[str]:
    errors: list[str] = []
    mission_control = manifest.get("mission_control", {})
    controller_enabled = bool(mission_control.get("agent_controller_enabled", False))
    if not controller_enabled:
        return errors

    controller_url = str(mission_control.get("agent_controller_url") or "").strip()
    if controller_url and not controller_url.startswith(("http://", "https://")):
        errors.append("mission_control.agent_controller_url must start with http:// or https://")

    example_env_path = ENV_DIR / "mission-control.env.example"
    local_env_path = ENV_DIR / "mission-control.env"
    if not local_env_path.exists():
        errors.append(
            "panopticon/env/mission-control.env is required when mission_control.agent_controller_enabled=true; set MC_AGENT_CONTROLLER_AUTH_TOKEN to a random long token and MC_AGENT_CONTROLLER_RISK_ACCEPTED=1"
        )
        return errors

    env_values = _load_env_file(example_env_path)
    env_values.update(_load_env_file(local_env_path))
    token = env_values.get("MC_AGENT_CONTROLLER_AUTH_TOKEN", "")
    if _is_placeholder_value(token) or len(str(token).strip()) < 32:
        errors.append(
            "panopticon/env/mission-control.env must set MC_AGENT_CONTROLLER_AUTH_TOKEN to a non-placeholder random token of at least 32 characters when mission_control.agent_controller_enabled=true"
        )
    if not _is_true_value(env_values.get("MC_AGENT_CONTROLLER_RISK_ACCEPTED", "")):
        errors.append(
            "panopticon/env/mission-control.env must set MC_AGENT_CONTROLLER_RISK_ACCEPTED=1 when mission_control.agent_controller_enabled=true because the controller mounts docker.sock"
        )
    return errors


def validate_local_environment(
    manifest: dict,
    *,
    strict_local: bool = False,
    check_host_ports: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def add_local_issue(message: str) -> None:
        if strict_local:
            errors.append(message)
        else:
            warnings.append(message)

    panopticon_env = _load_panopticon_environment()
    path_defaults = {
        "PANOPTICON_DATA_DIR": ".",
        "PANOPTICON_USB_HOST_PATH": "./shared-usb",
        "PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH": "./mission-control/knowledge-sources",
    }
    for name, default in path_defaults.items():
        raw_value = str(panopticon_env.get(name) or default).strip()
        path = _resolve_panopticon_path(raw_value)
        is_custom = name in panopticon_env
        if path.exists() and not path.is_dir():
            errors.append(f"{name} must point to a directory, got file: {path}")
        elif not path.exists() and (strict_local or is_custom):
            add_local_issue(f"{name} path does not exist yet: {path}")

    usb_container_path = str(panopticon_env.get("PANOPTICON_USB_CONTAINER_PATH") or "/mnt/usb").strip()
    if not usb_container_path.startswith("/"):
        errors.append("PANOPTICON_USB_CONTAINER_PATH must be an absolute container path")

    enabled_agents = [agent for agent in manifest.get("agents", []) if agent.get("enabled", True)]
    if strict_local:
        for agent in enabled_agents:
            slug = str(agent.get("slug") or "").strip()
            if slug and not (ENV_DIR / f"{slug}.env").exists():
                errors.append(f"missing local env override for enabled agent: panopticon/env/{slug}.env")

        for env_name in ["mission-control.env", "mission-control-ui.env", "mission-control-gateway.env"]:
            if not (ENV_DIR / env_name).exists():
                errors.append(f"missing local Mission Control env override: panopticon/env/{env_name}")

    if check_host_ports:
        mission_control = manifest.get("mission_control", {})
        ports: dict[int, str] = {}
        for key, label in [("api_port", "mission-control-api"), ("ui_port", "mission-control-ui")]:
            value = mission_control.get(key)
            if isinstance(value, int):
                ports[value] = label
        for agent in enabled_agents:
            slug = str(agent.get("slug") or "").strip()
            for key in ["gateway_host_port", "bridge_host_port"]:
                value = agent.get(key)
                if isinstance(value, int):
                    ports[value] = f"openclaw-{slug}.{key}"

        for port, label in sorted(ports.items()):
            if _host_port_accepts_connections(port):
                warnings.append(
                    f"host port {port} for {label} is already accepting connections; expected if the stack is already running"
                )

    return errors, warnings


def validate_generated_files(manifest: dict) -> list[str]:
    errors: list[str] = []

    if not COMPOSE_PATH.exists():
        errors.append(f"missing generated compose file: {COMPOSE_PATH}")
    else:
        compose_text = COMPOSE_PATH.read_text(encoding="utf-8")
        if "MC_WORKSPACES_DIR: /data/workspaces" not in compose_text:
            errors.append(
                "generated compose file is missing MC_WORKSPACES_DIR for mission-control-api"
            )
        if "source: ${PANOPTICON_DATA_DIR:-.}/workspaces\n        target: /data/workspaces" not in compose_text:
            errors.append(
                "generated compose file is missing PANOPTICON_DATA_DIR workspaces bind for mission-control-api"
            )

    for file_name in sorted(REQUIRED_STATIC_ENV_EXAMPLES):
        env_path = ENV_DIR / file_name
        if not env_path.exists():
            errors.append(f"missing static env example: {env_path}")

    enabled_agents = [a for a in manifest.get("agents", []) if a.get("enabled", True)]
    for agent in enabled_agents:
        slug = agent["slug"]
        env_path = ENV_DIR / f"{slug}.env.example"
        if not env_path.exists():
            errors.append(f"missing generated env file: {env_path}")

    return errors


def validate_release_alignment(manifest: dict, release: dict) -> list[str]:
    errors: list[str] = []

    runtime = manifest.get("agent_runtime", {})
    release_ports = release.get("ports", {})
    compat = release.get("compat", {})

    expected_pairs = [
        ("cnim_openclaw_version", str(release.get("openclaw_version", ""))),
        ("container_gateway_port", release_ports.get("panopticon_container_gateway_port")),
        ("container_bridge_port", release_ports.get("panopticon_container_bridge_port")),
        ("gateway_auth_mode", compat.get("gateway_auth_mode")),
        ("control_ui_disable_device_auth", compat.get("control_ui_disable_device_auth")),
    ]

    for key, expected in expected_pairs:
        if expected is None:
            continue
        actual = runtime.get(key)
        if str(actual) != str(expected):
            errors.append(
                f"release drift: agent_runtime.{key}={actual!r} does not match openclaw-release.yaml value {expected!r}"
            )

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
    parser.add_argument(
        "--release",
        type=Path,
        default=RELEASE_PATH,
        help="Path to openclaw-release.yaml",
    )
    parser.add_argument(
        "--strict-local",
        action="store_true",
        help="Also require local env overrides and local data paths to exist",
    )
    parser.add_argument(
        "--check-host-ports",
        action="store_true",
        help="Warn when generated host ports are already accepting connections",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    release = load_release(args.release)
    errors = validate_manifest(manifest)
    errors.extend(validate_generated_files(manifest))
    errors.extend(validate_release_alignment(manifest, release))
    errors.extend(validate_runtime_consistency(manifest))
    errors.extend(validate_controller_security(manifest))
    local_errors, warnings = validate_local_environment(
        manifest,
        strict_local=args.strict_local,
        check_host_ports=args.check_host_ports,
    )
    errors.extend(local_errors)

    if warnings:
        print("Validation warnings:")
        for item in warnings:
            print(f"- {item}")

    if errors:
        print("Validation failed:")
        for item in errors:
            print(f"- {item}")
        raise SystemExit(1)

    print("Validation passed.")
