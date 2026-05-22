from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "openclaw-release.yaml"


def load_release() -> dict:
    data = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("openclaw-release.yaml must be a mapping")
    return data


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def record_drift(drift_messages: list[str], path: Path, replacement: str) -> None:
    drift_messages.append(f"{relative_path(path)} should contain {replacement!r}")


def replace_pattern(
    path: Path,
    pattern: str,
    replacement: str,
    *,
    check: bool = False,
    drift_messages: list[str] | None = None,
) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"expected exactly one match in {path} for {pattern!r}")
    if updated == content:
        return
    if check:
        if drift_messages is not None:
            record_drift(drift_messages, path, replacement)
        return
    path.write_text(updated, encoding="utf-8")


def replace_any_pattern(
    path: Path,
    patterns: list[str],
    replacement: str,
    *,
    insert_after_pattern: str | None = None,
    check: bool = False,
    drift_messages: list[str] | None = None,
) -> None:
    content = path.read_text(encoding="utf-8")

    for pattern in patterns:
        updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
        if count == 1:
            if updated == content:
                return
            if check:
                if drift_messages is not None:
                    record_drift(drift_messages, path, replacement)
                return
            path.write_text(updated, encoding="utf-8")
            return

    if insert_after_pattern is None:
        raise ValueError(f"expected exactly one match in {path} for one of {patterns!r}")

    updated, count = re.subn(
        insert_after_pattern,
        lambda match: f"{match.group(0)}\n{replacement}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError(
            f"expected exactly one anchor match in {path} for {insert_after_pattern!r} when inserting {replacement!r}"
        )
    if check:
        if drift_messages is not None:
            record_drift(drift_messages, path, replacement)
        return
    path.write_text(updated, encoding="utf-8")


def sync_release(*, check: bool = False) -> list[str]:
    release = load_release()
    drift_messages: list[str] = []

    openclaw_version = str(release["openclaw_version"])
    gateway_port = int(release["ports"]["panopticon_container_gateway_port"])
    bridge_port = int(release["ports"]["panopticon_container_bridge_port"])
    compat = release["compat"]
    gateway_auth_mode = str(compat["gateway_auth_mode"])
    control_ui_disable = "true" if bool(compat["control_ui_disable_device_auth"]) else "false"

    legacy_chat_proxy_enabled = "1" if bool(compat.get("mission_control_legacy_chat_proxy_enabled", False)) else "0"
    direct_agent_links_enabled = "1" if bool(compat.get("mission_control_direct_agent_links_enabled", False)) else "0"
    chat_force_loopback_headers = "1" if bool(compat.get("mission_control_chat_force_loopback_headers", True)) else "0"
    chat_inject_script_enabled = "1" if bool(compat.get("mission_control_chat_inject_script_enabled", True)) else "0"
    chat_clear_device_auth_storage = "1" if bool(compat.get("mission_control_chat_clear_device_auth_storage", True)) else "0"
    chat_inject_gateway_settings = "1" if bool(compat.get("mission_control_chat_inject_gateway_settings", True)) else "0"
    chat_dom_avatar_rewrite = "1" if bool(compat.get("mission_control_chat_dom_avatar_rewrite", True)) else "0"
    chat_sanitize_connect_auth = "1" if bool(compat.get("mission_control_chat_sanitize_connect_auth", True)) else "0"
    chat_strip_stale_device_fields = "1" if bool(compat.get("mission_control_chat_strip_stale_device_fields", True)) else "0"
    chat_force_token_in_connect = "1" if bool(compat.get("mission_control_chat_force_token_in_connect", True)) else "0"
    chat_rewrite_control_ui_config = "1" if bool(compat.get("mission_control_chat_rewrite_control_ui_config", True)) else "0"
    chat_rewrite_avatar_payloads = "1" if bool(compat.get("mission_control_chat_rewrite_avatar_payloads", True)) else "0"

    replace_pattern(
        ROOT / "install.sh",
        r'^OPENCLAW_VERSION_DEFAULT="[^"]+"$',
        f'OPENCLAW_VERSION_DEFAULT="{openclaw_version}"',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "config-menu.sh",
        r'^DEFAULT_OPENCLAW_VERSION="[^"]+"$',
        f'DEFAULT_OPENCLAW_VERSION="{openclaw_version}"',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "Dockerfile",
        r'^ARG OPENCLAW_VERSION=[^\n]+$',
        f'ARG OPENCLAW_VERSION={openclaw_version}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "docker-compose.yml",
        r'OPENCLAW_VERSION: "[^"]+"',
        f'OPENCLAW_VERSION: "{openclaw_version}"',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "agents.manifest.yaml",
        r'^  cnim_openclaw_version: .+$',
        f'  cnim_openclaw_version: {openclaw_version}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "agents.manifest.yaml",
        r'^  container_gateway_port: .+$',
        f'  container_gateway_port: {gateway_port}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "agents.manifest.yaml",
        r'^  container_bridge_port: .+$',
        f'  container_bridge_port: {bridge_port}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "agents.manifest.yaml",
        r'^  gateway_auth_mode: .+$',
        f'  gateway_auth_mode: {gateway_auth_mode}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "agents.manifest.yaml",
        r'^  control_ui_disable_device_auth: .+$',
        f'  control_ui_disable_device_auth: {control_ui_disable}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "external" / "OpenClaw-Docker-CN-IM" / "Dockerfile",
        r'^ARG OPENCLAW_VERSION=[^\n]+$',
        f'ARG OPENCLAW_VERSION={openclaw_version}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control-ui.env.example",
        r'^MISSION_CONTROL_ENABLE_LEGACY_CHAT_PROXY=.+$',
        f'MISSION_CONTROL_ENABLE_LEGACY_CHAT_PROXY={legacy_chat_proxy_enabled}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_any_pattern(
        ROOT / "panopticon" / "env" / "mission-control-ui.env.example",
        [
            r'^MISSION_CONTROL_ENABLE_DIRECT_AGENT_LINKS=.+$',
            r'^MC_CHAT_ENABLE_DIRECT_AGENT_LINKS=.+$',
        ],
        f'MC_CHAT_ENABLE_DIRECT_AGENT_LINKS={direct_agent_links_enabled}',
        insert_after_pattern=r'^MISSION_CONTROL_ENABLE_LEGACY_CHAT_PROXY=.+$',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_UPSTREAM_PORT=.+$',
        f'MC_CHAT_UPSTREAM_PORT={gateway_port}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_PROXY_FORCE_LOOPBACK_HEADERS=.+$',
        f'MC_CHAT_PROXY_FORCE_LOOPBACK_HEADERS={chat_force_loopback_headers}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_INJECT_SCRIPT_ENABLED=.+$',
        f'MC_CHAT_COMPAT_INJECT_SCRIPT_ENABLED={chat_inject_script_enabled}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_CLEAR_DEVICE_AUTH_STORAGE=.+$',
        f'MC_CHAT_COMPAT_CLEAR_DEVICE_AUTH_STORAGE={chat_clear_device_auth_storage}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_INJECT_GATEWAY_SETTINGS=.+$',
        f'MC_CHAT_COMPAT_INJECT_GATEWAY_SETTINGS={chat_inject_gateway_settings}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_DOM_AVATAR_REWRITE=.+$',
        f'MC_CHAT_COMPAT_DOM_AVATAR_REWRITE={chat_dom_avatar_rewrite}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_SANITIZE_CONNECT_AUTH=.+$',
        f'MC_CHAT_COMPAT_SANITIZE_CONNECT_AUTH={chat_sanitize_connect_auth}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_STRIP_STALE_DEVICE_FIELDS=.+$',
        f'MC_CHAT_COMPAT_STRIP_STALE_DEVICE_FIELDS={chat_strip_stale_device_fields}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_FORCE_TOKEN_IN_CONNECT=.+$',
        f'MC_CHAT_COMPAT_FORCE_TOKEN_IN_CONNECT={chat_force_token_in_connect}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_REWRITE_CONTROL_UI_CONFIG=.+$',
        f'MC_CHAT_COMPAT_REWRITE_CONTROL_UI_CONFIG={chat_rewrite_control_ui_config}',
        check=check,
        drift_messages=drift_messages,
    )
    replace_pattern(
        ROOT / "panopticon" / "env" / "mission-control.env.example",
        r'^MC_CHAT_COMPAT_REWRITE_AVATAR_PAYLOADS=.+$',
        f'MC_CHAT_COMPAT_REWRITE_AVATAR_PAYLOADS={chat_rewrite_avatar_payloads}',
        check=check,
        drift_messages=drift_messages,
    )

    return drift_messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync OpenClaw release defaults into generated config files")
    parser.add_argument("--check", action="store_true", help="Fail if generated release defaults are out of sync")
    args = parser.parse_args()

    drift_messages = sync_release(check=args.check)

    if args.check:
        if drift_messages:
            print("Release defaults drift detected:")
            for message in drift_messages:
                print(f"- {message}")
            return 1
        print(f"Release defaults are in sync with {RELEASE_PATH}")
        return 0

    print(f"Synced release defaults from {RELEASE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
