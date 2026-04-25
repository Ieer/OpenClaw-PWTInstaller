from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".release-state"
RELEASE_PATH = ROOT / "openclaw-release.yaml"
COMPOSE_FILE = ROOT / "panopticon" / "docker-compose.panopticon.yml"
PYTHON = ROOT / ".venv" / "bin" / "python"
PREPARE_SCRIPT = ROOT / "tools" / "prepare_release_upgrade.py"
SMOKE_SCRIPT = ROOT / "panopticon" / "tools" / "smoke_chat_proxy.py"
AGENT_ENDPOINT_SCRIPT = ROOT / "panopticon" / "tools" / "check_agent_endpoints.sh"
PANOPTICON_HEALTH_SCRIPT = ROOT / "panopticon" / "tools" / "check_panopticon_services.sh"


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


def rollout_service(slug: str) -> str:
    return f"openclaw-{slug}"


def normalize_prepare_level(metadata: dict) -> str:
    prepare_level = str(metadata.get("prepare_level") or "").strip()
    if prepare_level in {"full", "light"}:
        return prepare_level

    mode = str(metadata.get("mode") or "release").strip()
    return "light" if mode == "fast-panopticon" else "full"


def normalize_verify_strategy(metadata: dict) -> str:
    verify_strategy = str(metadata.get("verify_strategy") or "").strip()
    if verify_strategy in {"none", "agent-endpoints", "panopticon", "smoke"}:
        return verify_strategy

    mode = str(metadata.get("mode") or "release").strip()
    return "agent-endpoints" if mode == "fast-panopticon" else "smoke"


def selected_agents_from_metadata(metadata: dict) -> list[str]:
    return [str(x) for x in metadata.get("selected_agents", []) if str(x).strip()]


def include_mission_control_from_metadata(metadata: dict) -> bool:
    return bool(metadata.get("include_mission_control", True))


def recreate_services_from_metadata(metadata: dict) -> list[str]:
    services = [str(x) for x in metadata.get("recreate_services", []) if str(x).strip()]
    if services:
        return services

    selected_agents = selected_agents_from_metadata(metadata)
    services = [rollout_service(slug) for slug in selected_agents]
    if include_mission_control_from_metadata(metadata):
        services = ["mission-control-api", "mission-control-ui", "mission-control-gateway", *services]
    return services


def collect_image_digests(services: list[str]) -> dict[str, str]:
    if not services:
        return {}

    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.Image}}", *services],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    digests = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(digests) != len(services):
        raise ValueError("docker inspect returned an unexpected number of image digests")
    return dict(zip(services, digests, strict=True))


def collect_runtime_versions(selected_agents: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    runtime_cmd = "openclaw --version 2>/dev/null || node -p 'require(\"/usr/local/lib/node_modules/openclaw/package.json\").version' 2>/dev/null"

    for slug in selected_agents:
        service = rollout_service(slug)
        result = subprocess.run(
            ["docker", "exec", service, "sh", "-lc", runtime_cmd],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip() or result.stderr.strip() or f"exit:{result.returncode}"
        versions[service] = output

    return versions


def summarize_runtime_version_changes(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], list[str]]:
    changed: list[str] = []
    unchanged: list[str] = []

    for service, post_version in after.items():
        if before.get(service) == post_version:
            unchanged.append(service)
        else:
            changed.append(service)

    return changed, unchanged


def build_runtime_version_rows(before: dict[str, str], after: dict[str, str]) -> list[dict[str, str | bool]]:
    services = sorted(set(before) | set(after))
    rows: list[dict[str, str | bool]] = []

    for service in services:
        before_version = before.get(service, "<missing>")
        after_version = after.get(service, "<missing>")
        status = "changed" if before_version != after_version else "unchanged"
        rows.append(
            {
                "service": service,
                "status": status,
                "before": before_version,
                "after": after_version,
                "changed": before_version != after_version,
            }
        )

    return rows


def render_runtime_version_table(before: dict[str, str], after: dict[str, str]) -> str:
    rows = build_runtime_version_rows(before, after)

    service_width = max(len("service"), *(len(str(row["service"])) for row in rows))
    status_width = max(len("status"), *(len(str(row["status"])) for row in rows))
    before_width = max(len("before"), *(len(str(row["before"])) for row in rows))

    header = (
        f"{'service':<{service_width}}  {'status':<{status_width}}  "
        f"{'before':<{before_width}}  after"
    )
    separator = (
        f"{'-' * service_width}  {'-' * status_width}  "
        f"{'-' * before_width}  {'-' * len('after')}"
    )
    body = [
        f"{row['service']:<{service_width}}  {row['status']:<{status_width}}  {row['before']:<{before_width}}  {row['after']}"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def enforce_runtime_version_gate(
    stage: str,
    before: dict[str, str],
    after: dict[str, str],
    changed: list[str],
    unchanged: list[str],
) -> None:
    if not unchanged:
        return

    print(f"[WARN] {stage}: runtime versions unchanged for {', '.join(unchanged)}")
    print(render_runtime_version_table(before, after))
    if not changed:
        raise SystemExit(f"{stage} failed: runtime versions unchanged for all selected services")


def write_rollout_metadata(metadata: dict[str, object]) -> None:
    metadata_path = STATE_DIR / "last-rollout.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_verify_step(verify_strategy: str, selected_agents: list[str], smoke_base_url: str) -> None:
    if verify_strategy == "none":
        print("==> Skip post-rollback verify")
        return

    if verify_strategy == "agent-endpoints":
        run_step("Post-rollback agent endpoint verify", ["bash", str(AGENT_ENDPOINT_SCRIPT), *selected_agents])
        return

    if verify_strategy == "panopticon":
        run_step("Post-rollback Panopticon health verify", ["bash", str(PANOPTICON_HEALTH_SCRIPT)])
        return

    if verify_strategy == "smoke":
        run_step(
            "Post-rollback smoke",
            [python_exe(), str(SMOKE_SCRIPT), "--base-url", smoke_base_url, *selected_agents],
        )
        return

    raise ValueError(f"unsupported verify strategy: {verify_strategy}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback the last OpenClaw release rollout")
    parser.add_argument("--snapshot", help="Optional explicit snapshot path relative to repo root or absolute path")
    parser.add_argument("--smoke-base-url", help="Optional override for the post-rollback gateway base URL")
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

    selected_agents = selected_agents_from_metadata(metadata)
    include_mission_control = include_mission_control_from_metadata(metadata)
    prepare_level = normalize_prepare_level(metadata)
    verify_strategy = normalize_verify_strategy(metadata)
    recreate_services = recreate_services_from_metadata(metadata)
    smoke_base_url = args.smoke_base_url or str(metadata.get("smoke_base_url") or "http://localhost:18920")
    pre_rollback_image_digests = collect_image_digests(recreate_services)
    pre_rollback_runtime_versions = collect_runtime_versions(selected_agents)

    print(f"Rollback mode: {metadata.get('mode', 'release')}")
    print(f"Prepare level: {prepare_level}")
    print(f"Verify strategy: {verify_strategy}")
    print(f"Include mission-control: {include_mission_control}")

    prepare_cmd = [python_exe(), str(PREPARE_SCRIPT), "--level", prepare_level, "--skip-smoke"]
    run_step("Prepare restored release", prepare_cmd)

    compose_base = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    recreate_cmd = [*compose_base, "up", "-d", "--force-recreate"]
    if not include_mission_control:
        recreate_cmd.append("--no-deps")
    recreate_cmd.extend(recreate_services)
    run_step("Recreate rollback services", recreate_cmd)

    post_rollback_image_digests = collect_image_digests(recreate_services)
    post_rollback_runtime_versions = collect_runtime_versions(selected_agents)
    changed_services, unchanged_services = summarize_runtime_version_changes(
        pre_rollback_runtime_versions,
        post_rollback_runtime_versions,
    )
    rollback_runtime_version_comparison_rows = build_runtime_version_rows(
        pre_rollback_runtime_versions,
        post_rollback_runtime_versions,
    )
    rollback_runtime_version_comparison_table = render_runtime_version_table(
        pre_rollback_runtime_versions,
        post_rollback_runtime_versions,
    )
    metadata["rollback_completed_at"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    metadata["rollback_snapshot"] = str(snapshot.relative_to(ROOT))
    metadata["rollback_prepare_level"] = prepare_level
    metadata["rollback_verify_strategy"] = verify_strategy
    metadata["rollback_recreate_services"] = recreate_services
    metadata["pre_rollback_image_digests"] = pre_rollback_image_digests
    metadata["pre_rollback_runtime_versions"] = pre_rollback_runtime_versions
    metadata["post_rollback_image_digests"] = post_rollback_image_digests
    metadata["post_rollback_runtime_versions"] = post_rollback_runtime_versions
    metadata["rollback_runtime_version_changed_services"] = changed_services
    metadata["rollback_runtime_version_unchanged_services"] = unchanged_services
    metadata["rollback_runtime_version_gate_passed"] = not unchanged_services or bool(changed_services)
    metadata["rollback_runtime_version_comparison_rows"] = rollback_runtime_version_comparison_rows
    metadata["rollback_runtime_version_comparison_table"] = rollback_runtime_version_comparison_table
    write_rollout_metadata(metadata)

    enforce_runtime_version_gate(
        "Rollback version gate",
        pre_rollback_runtime_versions,
        post_rollback_runtime_versions,
        changed_services,
        unchanged_services,
    )

    run_verify_step(verify_strategy, selected_agents, smoke_base_url)

    print("Runtime versions after rollback:")
    for service, version in post_rollback_runtime_versions.items():
        print(f"  {service}: {version}")

    print("Rollback completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
