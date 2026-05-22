#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import subprocess
from pathlib import Path
from typing import Iterable


PANOPTICON_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PANOPTICON_ROOT / "agents.manifest.yaml"
AGENT_HOMES_DIR = PANOPTICON_ROOT / "agent-homes"
DEFAULT_GATEWAY_PORT = 18920


def _run_capture(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def _is_lan_candidate(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not isinstance(address, ipaddress.IPv4Address):
        return False
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    )


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def detect_lan_ips() -> list[str]:
    values: list[str] = []

    ip_output = _run_capture(["ip", "-o", "-4", "addr", "show", "scope", "global"])
    for line in ip_output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        interface_name = parts[1]
        if interface_name.startswith(("docker", "br-", "veth")):
            continue
        try:
            address = parts[3].split("/", 1)[0]
        except IndexError:
            continue
        values.append(address)

    if not values:
        hostname_output = _run_capture(["hostname", "-I"])
        values.extend(hostname_output.split())

    return _unique(value for value in values if _is_lan_candidate(value))


def detect_hostnames() -> list[str]:
    values = [socket.gethostname(), socket.getfqdn()]
    for value in list(values):
        if value and "." not in value:
            values.append(f"{value}.local")
    return _unique(
        value
        for value in values
        if value and value not in {"localhost", "localhost.localdomain"}
    )


def load_gateway_port(manifest_path: Path = MANIFEST_PATH) -> int:
    if not manifest_path.exists():
        return DEFAULT_GATEWAY_PORT
    try:
        import yaml

        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        port = int(data.get("mission_control", {}).get("ui_port") or DEFAULT_GATEWAY_PORT)
        return port
    except Exception:
        pass

    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("ui_port:"):
            try:
                return int(stripped.split(":", 1)[1].strip().strip('"'))
            except ValueError:
                return DEFAULT_GATEWAY_PORT
    return DEFAULT_GATEWAY_PORT


def build_origins(
    *,
    port: int,
    ips: Iterable[str],
    hosts: Iterable[str],
    extra_origins: Iterable[str],
) -> list[str]:
    candidates = [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]
    candidates.extend(f"http://{ip}:{port}" for ip in ips)
    candidates.extend(f"http://{host}:{port}" for host in hosts)
    candidates.extend(extra_origins)
    return _unique(candidates)


def iter_openclaw_configs(agent_homes_dir: Path, selected_agents: set[str]) -> list[Path]:
    configs: list[Path] = []
    for path in sorted(agent_homes_dir.glob("*/openclaw.json")):
        agent = path.parent.name
        if selected_agents and agent not in selected_agents:
            continue
        configs.append(path)
    return configs


def sync_config(path: Path, origins: list[str], *, dry_run: bool) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    gateway = data.setdefault("gateway", {})
    control_ui = gateway.setdefault("controlUi", {})
    existing = control_ui.get("allowedOrigins")
    if not isinstance(existing, list):
        existing = []

    normalized_existing = _unique(str(item) for item in existing)
    missing = [origin for origin in origins if origin not in normalized_existing]
    if not missing:
        return []

    control_ui["allowedOrigins"] = normalized_existing + missing
    if not dry_run:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Mission Control LAN origins into every Panopticon agent openclaw.json."
    )
    parser.add_argument("--port", type=int, default=None, help="Mission Control gateway port; defaults to manifest ui_port.")
    parser.add_argument("--ip", action="append", default=[], help="Additional LAN IP to allow. Can be repeated.")
    parser.add_argument("--host", action="append", default=[], help="Additional hostname to allow. Can be repeated.")
    parser.add_argument("--origin", action="append", default=[], help="Exact extra origin to allow. Can be repeated.")
    parser.add_argument("--agent", action="append", default=[], help="Limit to one agent slug. Can be repeated.")
    parser.add_argument("--no-detect-hostnames", action="store_true", help="Do not add hostname and .local origins.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    args = parser.parse_args()

    port = args.port or load_gateway_port()
    ips = _unique([*detect_lan_ips(), *args.ip])
    hosts = _unique(args.host if args.no_detect_hostnames else [*detect_hostnames(), *args.host])
    origins = build_origins(port=port, ips=ips, hosts=hosts, extra_origins=args.origin)
    selected_agents = {agent.strip() for agent in args.agent if agent.strip()}

    configs = iter_openclaw_configs(AGENT_HOMES_DIR, selected_agents)
    if not configs:
        print("No openclaw.json files found.")
        return 1

    print(f"Mission Control gateway port: {port}")
    print("Candidate origins:")
    for origin in origins:
        print(f"  - {origin}")
    print()

    changed = 0
    for config_path in configs:
        missing = sync_config(config_path, origins, dry_run=args.dry_run)
        if not missing:
            print(f"OK {config_path.relative_to(PANOPTICON_ROOT)}")
            continue
        changed += 1
        action = "WOULD UPDATE" if args.dry_run else "UPDATED"
        print(f"{action} {config_path.relative_to(PANOPTICON_ROOT)}")
        for origin in missing:
            print(f"  + {origin}")

    if args.dry_run:
        print(f"Dry run complete. Files needing updates: {changed}")
    else:
        print(f"Sync complete. Updated files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
