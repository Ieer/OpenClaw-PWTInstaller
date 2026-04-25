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
PREPARE_SCRIPT = ROOT / "tools" / "prepare_release_upgrade.py"
SMOKE_SCRIPT = ROOT / "panopticon" / "tools" / "smoke_chat_proxy.py"
AGENT_ENDPOINT_SCRIPT = ROOT / "panopticon" / "tools" / "check_agent_endpoints.sh"
PANOPTICON_HEALTH_SCRIPT = ROOT / "panopticon" / "tools" / "check_panopticon_services.sh"


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


def rollout_service(slug: str) -> str:
    return f"openclaw-{slug}"


def normalize_prepare_level(mode: str, requested: str) -> str:
    if requested != "auto":
        return requested
    return "full" if mode == "release" else "light"


def normalize_verify_strategy(mode: str, requested: str) -> str:
    if requested != "auto":
        return requested
    return "smoke" if mode == "release" else "agent-endpoints"


def normalize_include_mission_control(mode: str, requested: bool | None) -> bool:
    if requested is not None:
        return requested
    return mode == "release"


def build_targets(selected_agents: list[str], include_mission_control: bool) -> list[str]:
    targets: list[str] = []
    if include_mission_control:
        targets.extend(["mission-control-api", "mission-control-ui"])
    if selected_agents:
        targets.append(rollout_service(selected_agents[0]))
    return targets


def recreate_services(selected_agents: list[str], include_mission_control: bool) -> list[str]:
    services = [rollout_service(slug) for slug in selected_agents]
    if include_mission_control:
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
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = STATE_DIR / "last-rollout.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot_release(
    selected_agents: list[str],
    include_mission_control: bool,
    *,
    mode: str,
    prepare_level: str,
    verify_strategy: str,
    build_targets: list[str],
    recreate_targets: list[str],
    smoke_base_url: str,
    pre_image_digests: dict[str, str],
    pre_runtime_versions: dict[str, str],
) -> tuple[Path, dict[str, object]]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release_snapshot = STATE_DIR / f"release-{stamp}.yaml"
    shutil.copy2(RELEASE_PATH, release_snapshot)
    metadata = {
        "created_at": stamp,
        "release_snapshot": str(release_snapshot.relative_to(ROOT)),
        "mode": mode,
        "prepare_level": prepare_level,
        "verify_strategy": verify_strategy,
        "selected_agents": selected_agents,
        "include_mission_control": include_mission_control,
        "build_targets": build_targets,
        "recreate_services": recreate_targets,
        "smoke_base_url": smoke_base_url,
        "pre_image_digests": pre_image_digests,
        "pre_runtime_versions": pre_runtime_versions,
    }
    write_rollout_metadata(metadata)
    return release_snapshot, metadata


def run_verify_step(verify_strategy: str, selected_agents: list[str], smoke_base_url: str) -> None:
    if verify_strategy == "none":
        print("==> Skip post-rollout verify")
        return

    if verify_strategy == "agent-endpoints":
        run_step("Post-rollout agent endpoint verify", ["bash", str(AGENT_ENDPOINT_SCRIPT), *selected_agents])
        return

    if verify_strategy == "panopticon":
        run_step("Post-rollout Panopticon health verify", ["bash", str(PANOPTICON_HEALTH_SCRIPT)])
        return

    if verify_strategy == "smoke":
        run_step(
            "Post-rollout smoke",
            [python_exe(), str(SMOKE_SCRIPT), "--base-url", smoke_base_url, *selected_agents],
        )
        return

    raise ValueError(f"unsupported verify strategy: {verify_strategy}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gray rollout OpenClaw release changes through Panopticon")
    parser.add_argument("agents", nargs="*", help="Agent slugs to rollout; default is all enabled agents")
    parser.add_argument(
        "--mode",
        choices=["release", "fast-panopticon"],
        default="release",
        help="Rollout mode: release keeps the existing full workflow, fast-panopticon only targets OpenClaw agent refresh",
    )
    parser.add_argument(
        "--prepare-level",
        choices=["auto", "full", "light"],
        default="auto",
        help="Preparation depth override; auto follows the selected mode",
    )
    parser.add_argument(
        "--verify",
        choices=["auto", "none", "agent-endpoints", "panopticon", "smoke"],
        default="auto",
        help="Post-rollout verification strategy; auto follows the selected mode",
    )
    parser.add_argument("--skip-prepare", action="store_true", help="Skip prepare_release_upgrade checks before rollout")
    parser.add_argument("--skip-build", action="store_true", help="Skip docker compose build step")
    mission_control_group = parser.add_mutually_exclusive_group()
    mission_control_group.add_argument(
        "--include-mission-control",
        dest="include_mission_control",
        action="store_true",
        help="Recreate mission-control services even in fast-panopticon mode",
    )
    mission_control_group.add_argument(
        "--no-mission-control",
        dest="include_mission_control",
        action="store_false",
        help="Do not recreate mission-control services",
    )
    parser.set_defaults(include_mission_control=None)
    parser.add_argument("--smoke-base-url", default="http://localhost:18920", help="Gateway base URL for post-rollout smoke test")
    args = parser.parse_args()

    selected_agents = args.agents or load_manifest_agents()
    prepare_level = normalize_prepare_level(args.mode, args.prepare_level)
    verify_strategy = normalize_verify_strategy(args.mode, args.verify)
    include_mission_control = normalize_include_mission_control(args.mode, args.include_mission_control)
    build_target_services = build_targets(selected_agents, include_mission_control)
    recreate_target_services = recreate_services(selected_agents, include_mission_control)
    pre_image_digests = collect_image_digests(recreate_target_services)
    pre_runtime_versions = collect_runtime_versions(selected_agents)

    print(f"Mode: {args.mode}")
    print(f"Prepare level: {prepare_level}")
    print(f"Verify strategy: {verify_strategy}")
    print(f"Include mission-control: {include_mission_control}")

    snapshot, metadata = snapshot_release(
        selected_agents,
        include_mission_control,
        mode=args.mode,
        prepare_level=prepare_level,
        verify_strategy=verify_strategy,
        build_targets=build_target_services,
        recreate_targets=recreate_target_services,
        smoke_base_url=args.smoke_base_url,
        pre_image_digests=pre_image_digests,
        pre_runtime_versions=pre_runtime_versions,
    )
    print(f"Saved rollback snapshot: {snapshot.relative_to(ROOT)}")

    if not args.skip_prepare:
        run_step(
            "Prepare release upgrade",
            [python_exe(), str(PREPARE_SCRIPT), "--level", prepare_level, "--skip-smoke"],
        )

    compose_base = ["docker", "compose", "-f", str(COMPOSE_FILE)]

    if not args.skip_build and build_target_services:
        run_step("Build selected services", [*compose_base, "build", *build_target_services])

    recreate_cmd = [*compose_base, "up", "-d", "--force-recreate"]
    if not include_mission_control:
        recreate_cmd.append("--no-deps")
    recreate_cmd.extend(recreate_target_services)
    run_step("Recreate selected services", recreate_cmd)

    post_image_digests = collect_image_digests(recreate_target_services)
    post_runtime_versions = collect_runtime_versions(selected_agents)
    changed_services, unchanged_services = summarize_runtime_version_changes(pre_runtime_versions, post_runtime_versions)
    runtime_version_comparison_rows = build_runtime_version_rows(pre_runtime_versions, post_runtime_versions)
    runtime_version_comparison_table = render_runtime_version_table(pre_runtime_versions, post_runtime_versions)
    metadata["post_image_digests"] = post_image_digests
    metadata["post_runtime_versions"] = post_runtime_versions
    metadata["runtime_version_changed_services"] = changed_services
    metadata["runtime_version_unchanged_services"] = unchanged_services
    metadata["runtime_version_gate_passed"] = not unchanged_services or bool(changed_services)
    metadata["runtime_version_comparison_rows"] = runtime_version_comparison_rows
    metadata["runtime_version_comparison_table"] = runtime_version_comparison_table
    write_rollout_metadata(metadata)

    enforce_runtime_version_gate(
        "Rollout version gate",
        pre_runtime_versions,
        post_runtime_versions,
        changed_services,
        unchanged_services,
    )

    run_verify_step(verify_strategy, selected_agents, args.smoke_base_url)

    print("Runtime versions after rollout:")
    for service, version in post_runtime_versions.items():
        print(f"  {service}: {version}")

    print("Rollout completed.")
    print("If you need to undo this rollout, run: python tools/rollback_release_upgrade.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
