from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml


DEFAULT_AGENTS = [
    "nox",
    "metrics",
    "email",
    "growth",
    "trades",
    "health",
    "writing",
    "personal",
]

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "agents.manifest.yaml"


@dataclass
class CheckResult:
    agent: str
    http_status: str
    ws_status: str


def _load_default_agents() -> list[str]:
    if not MANIFEST_PATH.exists():
        return DEFAULT_AGENTS
    try:
        data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_AGENTS
    if not isinstance(data, dict):
        return DEFAULT_AGENTS
    agents = data.get("agents")
    if not isinstance(agents, list):
        return DEFAULT_AGENTS
    out: list[str] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        if not item.get("enabled", True):
            continue
        slug = str(item.get("slug") or "").strip()
        if slug:
            out.append(slug)
    return out or DEFAULT_AGENTS


def _http_check(base_url: str, agent: str, timeout: float) -> str:
    url = f"{base_url.rstrip('/')}/chat/{agent}/"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return f"HTTP:{resp.status}"
    except HTTPError as exc:
        return f"HTTP:{exc.code}"
    except URLError as exc:
        return f"HTTP_FAIL:{exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return f"HTTP_FAIL:{type(exc).__name__}:{exc}"


async def _ws_check(base_url: str, agent: str, timeout: float) -> str:
    try:
        import websockets
    except Exception:
        return "WS_SKIP:websockets-not-installed"

    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc
    url = f"{scheme}://{netloc}/chat/{agent}/"

    try:
        async with websockets.connect(url, open_timeout=timeout, close_timeout=2):
            return "WS_OK"
    except Exception as exc:  # noqa: BLE001
        return f"WS_FAIL:{type(exc).__name__}:{exc}"


async def _run(base_url: str, agents: Iterable[str], timeout: float) -> list[CheckResult]:
    out: list[CheckResult] = []
    for agent in agents:
        http_status = _http_check(base_url, agent, timeout)
        ws_status = await _ws_check(base_url, agent, timeout)
        out.append(CheckResult(agent=agent, http_status=http_status, ws_status=ws_status))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Mission Control /chat proxy")
    parser.add_argument("--base-url", default="http://localhost:18920", help="Gateway base URL")
    parser.add_argument("--timeout", type=float, default=8.0, help="Timeout in seconds")
    parser.add_argument("agents", nargs="*", default=_load_default_agents(), help="Agent slugs to check")
    args = parser.parse_args()

    results = asyncio.run(_run(args.base_url, args.agents, args.timeout))

    failed = False
    for item in results:
        print(f"{item.agent}|{item.http_status}|{item.ws_status}")
        if item.http_status != "HTTP:200":
            failed = True
        if item.ws_status.startswith("WS_FAIL"):
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
