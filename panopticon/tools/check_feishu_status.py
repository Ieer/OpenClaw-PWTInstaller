#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "panopticon" / "agents.manifest.yaml"
COMMUNITY_FEISHU_DIR = "/home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu"
COMMUNITY_FEISHU_INSTALL_PATH = COMMUNITY_FEISHU_DIR
EXPECTED_COMMUNITY_FEISHU_VERSION = "0.1.18"

SUCCESS_PATTERNS = {
    "runtime": re.compile(r"loading feishu from", re.IGNORECASE),
    "gateway": re.compile(r"http server listening .*\bfeishu\b", re.IGNORECASE),
    "websocket": re.compile(r"feishu\[[^\]]+\]: WebSocket client started", re.IGNORECASE),
}

FAILURE_PATTERNS = [
    ("plugin-not-found", re.compile(r"plugin not found: feishu", re.IGNORECASE)),
    ("compiled-runtime-missing", re.compile(r"requires compiled runtime output.*feishu|feishu.*requires compiled runtime output", re.IGNORECASE)),
    ("channel-configs-missing", re.compile(r"channel plugin manifest declares feishu without channelConfigs", re.IGNORECASE)),
    ("contracts-tools-missing", re.compile(r"feishu.*contracts\.tools|contracts\.tools.*feishu|feishu.*must declare contracts\.tools|must declare contracts\.tools.*feishu", re.IGNORECASE)),
    ("module-missing", re.compile(r"Cannot find (?:module|package).*feishu|feishu.*Cannot find (?:module|package)", re.IGNORECASE)),
    ("root-alias-missing", re.compile(r"root-alias\.cjs/feishu", re.IGNORECASE)),
    ("plugin-load-failed", re.compile(r"failed to load .*feishu|feishu.*failed to load", re.IGNORECASE)),
    ("websocket-disconnected", re.compile(r"feishu.*websocket.*(?:abort|closed|disconnect|disconnected)|(?:abort|closed|disconnect|disconnected).*feishu.*websocket", re.IGNORECASE)),
]


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class AgentCheck:
    agent: str
    container: str
    status: str = "fail"
    config: str = "fail"
    plugin: str = "fail"
    runtime: str = "fail"
    websocket: str = "fail"
    source: str = "unknown"
    configured: bool = False
    reasons: list[str] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def fail(self, reason: str, advice: str | None = None) -> None:
        self.reasons.append(reason)
        if advice and advice not in self.advice:
            self.advice.append(advice)

    def to_json(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "container": self.container,
            "status": self.status,
            "configured": self.configured,
            "config": self.config,
            "plugin": self.plugin,
            "runtime": self.runtime,
            "websocket": self.websocket,
            "source": self.source,
            "reasons": self.reasons,
            "advice": self.advice,
            "details": self.details,
        }


def run_cmd(args: list[str], *, timeout: int = 30) -> CommandResult:
    result = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(result.returncode, result.stdout, result.stderr)


def docker(args: list[str], *, timeout: int = 30) -> CommandResult:
    return run_cmd(["docker", *args], timeout=timeout)


def load_manifest_agents() -> list[str]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST_PATH} must be a mapping")
    agents = data.get("agents")
    if not isinstance(agents, list):
        raise ValueError("agents.manifest.yaml must contain an agents list")

    slugs: list[str] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        if not item.get("enabled", True):
            continue
        slug = str(item.get("slug") or "").strip()
        if slug:
            slugs.append(slug)
    return slugs


def validate_agents(selected_agents: list[str]) -> None:
    enabled = set(load_manifest_agents())
    invalid = [agent for agent in selected_agents if agent not in enabled]
    if invalid:
        raise SystemExit(
            "unknown or disabled agent slug(s): "
            + ", ".join(invalid)
            + f"; enabled agents: {', '.join(sorted(enabled))}"
        )


def service_name(agent: str) -> str:
    return f"openclaw-{agent}"


def inspect_running(container: str) -> bool:
    result = docker(["inspect", "-f", "{{.State.Running}}", container])
    return result.returncode == 0 and result.stdout.strip() == "true"


def inspect_started_at(container: str) -> str | None:
    result = docker(["inspect", "-f", "{{.State.StartedAt}}", container])
    if result.returncode != 0:
        return None
    started_at = result.stdout.strip()
    return started_at if started_at and started_at != "<no value>" else None


def exec_json(container: str, script: str, *, timeout: int = 30) -> dict[str, Any]:
    result = docker(["exec", container, "node", "-e", script], timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"docker exec failed for {container}").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"docker exec returned non-JSON output for {container}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"docker exec returned unexpected payload for {container}")
    return payload


def collect_container_state(container: str) -> dict[str, Any]:
    script = r'''
const fs = require('fs');
const path = require('path');

function exists(filePath) {
  try { return fs.existsSync(filePath); } catch { return false; }
}

function readJson(filePath) {
  try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); } catch { return null; }
}

const configPath = '/home/node/.openclaw/openclaw.json';
const config = readJson(configPath) || {};
const channels = config.channels && typeof config.channels === 'object' ? config.channels : {};
const feishu = channels.feishu && typeof channels.feishu === 'object' ? channels.feishu : null;
const plugins = config.plugins && typeof config.plugins === 'object' ? config.plugins : {};
const entries = plugins.entries && typeof plugins.entries === 'object' ? plugins.entries : {};
const feishuEntry = entries.feishu && typeof entries.feishu === 'object' ? entries.feishu : null;
const allow = Array.isArray(plugins.allow) ? plugins.allow : [];

const stockCandidates = [
  '/usr/local/lib/node_modules/openclaw/dist/extensions/feishu',
  '/usr/local/lib/node_modules/openclaw/extensions/feishu',
];
const stockPath = stockCandidates.find((candidate) => exists(path.join(candidate, 'index.js')) || exists(path.join(candidate, 'index.ts')) || exists(path.join(candidate, 'openclaw.plugin.json'))) || '';

const communityDir = '/home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu';
const communityPackage = readJson(path.join(communityDir, 'package.json')) || {};
const communityManifest = readJson(path.join(communityDir, 'openclaw.plugin.json')) || {};
const registry = readJson('/home/node/.openclaw/plugins/installs.json') || {};
const installRecords = registry.installRecords && typeof registry.installRecords === 'object' ? registry.installRecords : {};
const installRecord = installRecords.feishu && typeof installRecords.feishu === 'object' ? installRecords.feishu : null;
const registryPlugins = Array.isArray(registry.plugins) ? registry.plugins : [];

const tools = communityManifest.contracts && Array.isArray(communityManifest.contracts.tools)
  ? communityManifest.contracts.tools
  : [];

const payload = {
  configPathExists: exists(configPath),
  feishu: {
    exists: Boolean(feishu),
    enabled: feishu ? feishu.enabled !== false : false,
    hasAppId: Boolean(feishu && feishu.appId),
    hasAppSecret: Boolean(feishu && feishu.appSecret),
    connectionMode: feishu && feishu.connectionMode ? String(feishu.connectionMode) : '',
    dmPolicy: feishu && feishu.dmPolicy ? String(feishu.dmPolicy) : '',
    groupPolicy: feishu && feishu.groupPolicy ? String(feishu.groupPolicy) : '',
  },
  plugins: {
    entryExists: Boolean(feishuEntry),
    entryEnabled: feishuEntry ? feishuEntry.enabled !== false : false,
    allowIsList: Array.isArray(plugins.allow),
    allowHasFeishu: allow.includes('feishu'),
  },
  stock: {
    available: Boolean(stockPath),
    path: stockPath,
    hasIndexJs: stockPath ? exists(path.join(stockPath, 'index.js')) : false,
    hasIndexTs: stockPath ? exists(path.join(stockPath, 'index.ts')) : false,
  },
  community: {
    packageExists: exists(path.join(communityDir, 'package.json')),
    version: communityPackage.version || '',
    hasIndexJs: exists(path.join(communityDir, 'index.js')),
    hasIndexTs: exists(path.join(communityDir, 'index.ts')),
    hasManifest: exists(path.join(communityDir, 'openclaw.plugin.json')),
    hasChannelConfigs: Boolean(communityManifest.channelConfigs && communityManifest.channelConfigs.feishu),
    toolCount: tools.length,
    installPath: installRecord && installRecord.installPath ? String(installRecord.installPath) : '',
    installPathOk: Boolean(installRecord && installRecord.installPath === communityDir),
    registryPluginPresent: registryPlugins.some((plugin) => plugin && plugin.pluginId === 'feishu'),
  },
};

console.log(JSON.stringify(payload));
'''
    return exec_json(container, script)


def collect_feishu_credentials(container: str) -> dict[str, str]:
    script = r'''
const fs = require('fs');
function readJson(filePath) {
  try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); } catch { return null; }
}
const config = readJson('/home/node/.openclaw/openclaw.json') || {};
const feishu = config.channels && config.channels.feishu && typeof config.channels.feishu === 'object'
  ? config.channels.feishu
  : {};
console.log(JSON.stringify({ appId: feishu.appId || '', appSecret: feishu.appSecret || '' }));
'''
    payload = exec_json(container, script)
    return {
        "appId": str(payload.get("appId") or ""),
        "appSecret": str(payload.get("appSecret") or ""),
    }


def docker_logs(container: str, *, since: str | None, tail: int) -> tuple[str, str]:
    args = ["logs"]
    source = "all"
    if since:
        args.extend(["--since", since])
        source = f"since:{since}"
    args.append(container)
    result = docker(args, timeout=60)
    text = result.stdout + result.stderr

    if tail > 0 and not all(pattern.search(text) for pattern in SUCCESS_PATTERNS.values()):
        tail_result = docker(["logs", "--tail", str(tail), container], timeout=60)
        tail_text = tail_result.stdout + tail_result.stderr
        if len(tail_text) > len(text) or any(pattern.search(tail_text) for pattern in SUCCESS_PATTERNS.values()):
            text = tail_text
            source = f"tail:{tail}"

    return text, source


def analyze_config(agent: AgentCheck, state: dict[str, Any], require_configured: bool) -> bool:
    feishu = state.get("feishu") if isinstance(state.get("feishu"), dict) else {}
    plugins = state.get("plugins") if isinstance(state.get("plugins"), dict) else {}

    if not state.get("configPathExists"):
        agent.fail("openclaw.json is missing", "Recreate the agent container or inspect the mounted agent home.")
        return False

    if not feishu.get("exists") or not feishu.get("enabled"):
        agent.config = "skip"
        agent.plugin = "skip"
        agent.runtime = "skip"
        agent.websocket = "skip"
        if require_configured:
            agent.fail("Feishu is not configured or not enabled", "Set FEISHU_APP_ID/FEISHU_APP_SECRET or channels.feishu before the rollout check.")
            return False
        agent.status = "skip"
        agent.reasons.append("Feishu is not configured; skipped")
        return False

    agent.configured = True
    config_ok = True
    if not feishu.get("hasAppId"):
        config_ok = False
        agent.fail("channels.feishu.appId is missing", "Merge Feishu env vars into openclaw.json or rerun init.sh.")
    if not feishu.get("hasAppSecret"):
        config_ok = False
        agent.fail("channels.feishu.appSecret is missing", "Merge Feishu env vars into openclaw.json or rerun init.sh.")
    if not plugins.get("entryExists") or not plugins.get("entryEnabled"):
        config_ok = False
        agent.fail("plugins.entries.feishu is missing or disabled", "Ensure init.sh enables plugins.entries.feishu for configured Feishu agents.")
    if not plugins.get("allowHasFeishu"):
        config_ok = False
        agent.fail("plugins.allow does not include feishu", "Ensure init.sh appends feishu to plugins.allow when Feishu is configured.")

    agent.config = "pass" if config_ok else "fail"
    return config_ok


def analyze_plugin(agent: AgentCheck, state: dict[str, Any], expected_version: str) -> None:
    stock = state.get("stock") if isinstance(state.get("stock"), dict) else {}
    community = state.get("community") if isinstance(state.get("community"), dict) else {}

    if stock.get("available"):
        agent.source = f"stock:{stock.get('path') or 'feishu'}"
        agent.plugin = "pass"
        return

    agent.source = f"community:{community.get('version') or 'missing'}"
    plugin_ok = True
    if not community.get("packageExists"):
        plugin_ok = False
        agent.fail("community Feishu fallback package is missing", "Rebuild the CN-IM image and recreate the agent container.")
    if community.get("version") != expected_version:
        plugin_ok = False
        agent.fail(
            f"community Feishu fallback version is {community.get('version') or 'missing'}, expected {expected_version}",
            "Use @m1heng-clawd/feishu@0.1.18 for OpenClaw 2026.5.x.",
        )
    if not community.get("installPathOk") or not community.get("registryPluginPresent"):
        plugin_ok = False
        agent.fail("Feishu plugin registry install record is missing or points to the wrong path", "Restore the image plugin cache or rerun init.sh registration repair.")
    if not community.get("hasIndexJs"):
        plugin_ok = False
        agent.fail("community Feishu fallback is missing compiled index.js", "Run the OpenClaw 2026.5.x runtime repair or rebuild the CN-IM image.")
    if not community.get("hasChannelConfigs"):
        plugin_ok = False
        agent.fail("community Feishu manifest is missing channelConfigs.feishu", "Run the manifest metadata repair in init.sh.")
    if int(community.get("toolCount") or 0) <= 0:
        plugin_ok = False
        agent.fail("community Feishu manifest has no contracts.tools", "Run the contracts.tools repair in init.sh.")

    agent.plugin = "pass" if plugin_ok else "fail"


def analyze_logs(agent: AgentCheck, text: str, source: str) -> None:
    agent.details["logSource"] = source
    matched_failures = []
    for line in text.splitlines():
        for name, pattern in FAILURE_PATTERNS:
            if pattern.search(line) and name not in matched_failures:
                matched_failures.append(name)

    if matched_failures:
        for name in matched_failures:
            agent.fail(f"Feishu loader/runtime log failure: {name}", "Inspect docker logs for the agent and rebuild/recreate if the failure is from stale runtime files.")

    runtime_ok = bool(SUCCESS_PATTERNS["runtime"].search(text) and SUCCESS_PATTERNS["gateway"].search(text))
    websocket_ok = bool(SUCCESS_PATTERNS["websocket"].search(text))

    if not runtime_ok:
        agent.fail("Feishu did not appear in gateway plugin loading/listening logs", "Check plugin registration and fallback package readiness.")
    if not websocket_ok:
        agent.fail("Feishu WebSocket client started log was not found", "Check Feishu credentials, event subscription, and recent gateway logs.")

    agent.runtime = "pass" if runtime_ok and not matched_failures else "fail"
    agent.websocket = "pass" if websocket_ok and not matched_failures else "fail"


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Feishu API returned a non-object JSON payload")
    return data


def get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Feishu API returned a non-object JSON payload")
    return data


def analyze_active_api(agent: AgentCheck, container: str, send_chat_id: str | None) -> None:
    try:
        credentials = collect_feishu_credentials(container)
        if not credentials["appId"] or not credentials["appSecret"]:
            raise RuntimeError("Feishu App ID/App Secret are missing from openclaw.json")

        token_payload = post_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": credentials["appId"], "app_secret": credentials["appSecret"]},
        )
        if token_payload.get("code") != 0:
            raise RuntimeError(f"tenant_access_token failed: {token_payload.get('msg') or token_payload}")
        token = str(token_payload.get("tenant_access_token") or "")
        if not token:
            raise RuntimeError("tenant_access_token response did not include a token")

        bot_payload = get_json(
            "https://open.feishu.cn/open-apis/bot/v3/info",
            {"Authorization": f"Bearer {token}"},
        )
        agent.details["activeApi"] = {
            "token": "pass",
            "botInfo": "pass" if bot_payload.get("code") == 0 else "warn",
        }

        if send_chat_id:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
            content = json.dumps({"text": f"OpenClaw Feishu post-upgrade status check passed at {now}"}, ensure_ascii=False)
            send_payload = post_json(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                {"receive_id": send_chat_id, "msg_type": "text", "content": content},
                {"Authorization": f"Bearer {token}"},
            )
            if send_payload.get("code") != 0:
                raise RuntimeError(f"Feishu send test failed: {send_payload.get('msg') or send_payload}")
            agent.details["activeApi"]["send"] = "pass"
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        agent.fail(f"active Feishu API check failed: {exc}", "Verify App credentials, bot permissions, Feishu network access, and optional chat_id.")
        agent.details["activeApi"] = {"status": "fail"}


def check_agent(agent_slug: str, args: argparse.Namespace) -> AgentCheck:
    container = service_name(agent_slug)
    check = AgentCheck(agent=agent_slug, container=container)

    if not inspect_running(container):
        check.fail("container is not running", f"Start or recreate {container} before checking Feishu status.")
        return check

    try:
        state = collect_container_state(container)
    except RuntimeError as exc:
        check.fail(str(exc), "Ensure the container has node available and the OpenClaw home is mounted.")
        return check

    check.details["state"] = state
    config_ok = analyze_config(check, state, args.require_configured)
    if check.status == "skip":
        return check

    analyze_plugin(check, state, args.expected_community_version)

    since = args.since or inspect_started_at(container)
    log_text, log_source = docker_logs(container, since=since, tail=args.tail)
    analyze_logs(check, log_text, log_source)

    if args.active_api:
        analyze_active_api(check, container, args.send_chat_id)

    if config_ok and check.plugin == "pass" and check.runtime == "pass" and check.websocket == "pass" and not check.reasons:
        check.status = "pass"
    elif check.configured:
        check.status = "fail"
    return check


def truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def print_table(checks: list[AgentCheck]) -> None:
    headers = ["agent", "status", "config", "plugin", "runtime", "websocket", "source", "reason"]
    rows = []
    for check in checks:
        rows.append(
            [
                check.agent,
                check.status,
                check.config,
                check.plugin,
                check.runtime,
                check.websocket,
                truncate(check.source, 34),
                truncate("; ".join(check.reasons), 80),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    print("=== Feishu Status ===")
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def summary(checks: list[AgentCheck]) -> dict[str, Any]:
    counts = {"pass": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    return {
        "total": len(checks),
        "passed": counts.get("pass", 0),
        "failed": counts.get("fail", 0),
        "skipped": counts.get("skip", 0),
        "agents": [check.to_json() for check in checks],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Feishu runtime status for Panopticon OpenClaw agents")
    parser.add_argument("agents", nargs="*", help="Agent slugs to check; default is all enabled agents")
    parser.add_argument("--since", default="", help="docker logs --since value; default uses each container StartedAt")
    parser.add_argument("--tail", type=int, default=800, help="Fallback docker logs --tail line count when success markers are missing")
    parser.add_argument("--require-configured", action="store_true", help="Fail agents that do not have Feishu configured instead of skipping them")
    parser.add_argument("--expected-community-version", default=EXPECTED_COMMUNITY_FEISHU_VERSION, help="Expected @m1heng-clawd/feishu fallback version")
    parser.add_argument("--active-api", action="store_true", help="Also call Feishu tenant_access_token and bot info APIs")
    parser.add_argument("--send-chat-id", help="With --active-api, send a test message to this chat_id")
    parser.add_argument("--json", action="store_true", help="Print the full JSON result instead of the table")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    agents = args.agents or load_manifest_agents()
    validate_agents(agents)

    checks = [check_agent(agent, args) for agent in agents]
    payload = summary(checks)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_table(checks)
        compact = {key: payload[key] for key in ("total", "passed", "failed", "skipped")}
        print("Summary JSON: " + json.dumps(compact, ensure_ascii=False, sort_keys=True))

    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())