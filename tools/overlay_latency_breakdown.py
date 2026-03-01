#!/usr/bin/env python3
import argparse
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

import requests
import websocket


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso_to_ms(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        return dt.timestamp() * 1000.0
    except Exception:
        return 0.0


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return s[lo]
    return s[lo] * (hi - k) + s[hi] * (k - lo)


def summary(label: str, values: List[float]) -> str:
    if not values:
        return f"{label}: n=0"
    return (
        f"{label}: n={len(values)} "
        f"p50={percentile(values, 0.50):.1f}ms "
        f"p95={percentile(values, 0.95):.1f}ms "
        f"p99={percentile(values, 0.99):.1f}ms "
        f"max={max(values):.1f}ms"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Overlay latency breakdown: API ingest / WS / Feed / UI estimate")
    parser.add_argument("--api-url", default=os.getenv("MISSION_CONTROL_API_URL", "http://127.0.0.1:18910"))
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--agent", default="nox")
    parser.add_argument("--ui-tick-ms", type=float, default=1000.0)
    parser.add_argument("--render-ms", type=float, default=120.0)
    parser.add_argument("--gap-ms", type=float, default=120.0)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--token", default=(os.getenv("MISSION_CONTROL_AUTH_TOKEN") or os.getenv("MC_AUTH_TOKEN") or "").strip())
    parser.add_argument("--feed-path", default="/v1/feed-lite?limit=250")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    ws_base = urlparse(api_url)
    ws_scheme = "wss" if ws_base.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{(ws_base.netloc or ws_base.path).rstrip('/')}/ws/events"

    test_id = f"lat-breakdown-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    print(f"[info] test_id={test_id}")
    print(f"[info] api={api_url}")
    print(f"[info] ws={ws_url}")

    headers = {"Content-Type": "application/json"}
    ws_headers = []
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
        ws_headers.append(f"Authorization: Bearer {args.token}")

    # round -> times
    sent_ms: Dict[int, float] = {}
    api_return_ms: Dict[int, float] = {}
    api_created_ms: Dict[int, float] = {}
    ws_seen_ms: Dict[int, float] = {}
    feed_seen_ms: Dict[int, float] = {}

    lock = threading.Lock()
    connected = threading.Event()

    def on_open(_ws):
        connected.set()

    def on_message(_ws, message: str):
        now = time.time() * 1000.0
        try:
            item = json.loads(message)
        except Exception:
            return
        if not isinstance(item, dict):
            return
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if str(payload.get("test_id") or "") != test_id:
            return
        if str(item.get("type") or "") != "chat.message.sent":
            return
        round_idx = int(payload.get("round") or -1)
        if round_idx <= 0:
            return
        with lock:
            if round_idx not in ws_seen_ms:
                ws_seen_ms[round_idx] = now

    ws_app = websocket.WebSocketApp(
        ws_url,
        header=ws_headers,
        on_open=on_open,
        on_message=on_message,
        on_error=lambda _ws, err: print(f"[ws-error] {err}"),
        on_close=lambda _ws, _code, _msg: None,
    )
    ws_thread = threading.Thread(target=lambda: ws_app.run_forever(ping_interval=20, ping_timeout=10), daemon=True)
    ws_thread.start()

    if not connected.wait(timeout=8):
        print("[error] websocket connection timeout")
        return 2

    sess = requests.Session()
    print(f"[info] injecting rounds={args.rounds} (chat.message.sent)")

    for i in range(1, args.rounds + 1):
        now_ms = time.time() * 1000.0
        payload = {
            "test_id": test_id,
            "round": i,
            "client_sent_at": iso_now(),
            "client_sent_ms": now_ms,
            "method": "POST",
            "path": "/chat",
        }
        sent_ms[i] = now_ms

        resp = sess.post(
            f"{api_url}/v1/events",
            headers=headers,
            json={"type": "chat.message.sent", "agent": args.agent, "payload": payload},
            timeout=6,
        )
        ret_ms = time.time() * 1000.0
        api_return_ms[i] = ret_ms
        resp.raise_for_status()

        body = resp.json() if resp.content else {}
        created_ms = parse_iso_to_ms(str(body.get("created_at") or ""))
        api_created_ms[i] = created_ms if created_ms > 0 else ret_ms

        time.sleep(max(0.02, args.gap_ms / 1000.0))

    deadline = time.time() + args.timeout_s
    while time.time() < deadline:
        # feed polling
        try:
            feed = sess.get(f"{api_url}{args.feed_path}", headers=headers, timeout=5).json()
        except Exception:
            feed = []
        now_ms = time.time() * 1000.0
        if isinstance(feed, list):
            for item in feed:
                if str(item.get("type") or "") != "chat.message.sent":
                    continue
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                top_test_id = str(item.get("test_id") or "")
                test_ref = str(payload.get("test_id") or top_test_id or "")
                if test_ref != test_id:
                    continue
                top_round = item.get("round")
                round_idx = int(payload.get("round") or top_round or -1)
                if round_idx > 0 and round_idx not in feed_seen_ms:
                    feed_seen_ms[round_idx] = now_ms

        if len(feed_seen_ms) >= args.rounds and len(ws_seen_ms) >= args.rounds:
            break
        time.sleep(0.08)

    try:
        ws_app.close()
    except Exception:
        pass

    api_rtt: List[float] = []
    api_ingest: List[float] = []
    ws_delivery: List[float] = []
    feed_visibility: List[float] = []
    ui_refresh_est: List[float] = []

    missing_ws = 0
    missing_feed = 0

    for i in range(1, args.rounds + 1):
        s = sent_ms.get(i, 0.0)
        r = api_return_ms.get(i, 0.0)
        c = api_created_ms.get(i, 0.0)
        if s > 0 and r > 0:
            api_rtt.append(max(0.0, r - s))
        if s > 0 and c > 0:
            api_ingest.append(max(0.0, c - s))

        w = ws_seen_ms.get(i)
        if w is None:
            missing_ws += 1
        else:
            ws_delivery.append(max(0.0, w - s))
            ui_refresh_est.append(max(0.0, (w - s) + args.ui_tick_ms + args.render_ms))

        f = feed_seen_ms.get(i)
        if f is None:
            missing_feed += 1
        else:
            feed_visibility.append(max(0.0, f - s))

    print("\n=== Latency Breakdown Report ===")
    print(f"test_id: {test_id}")
    print(f"rounds: {args.rounds}")
    print(f"missing_ws: {missing_ws}")
    print(f"missing_feed: {missing_feed}")
    print(summary("api_rtt_ms", api_rtt))
    print(summary("api_ingest_ms", api_ingest))
    print(summary("ws_delivery_ms", ws_delivery))
    print(summary("feed_visibility_ms", feed_visibility))
    print(summary("ui_refresh_est_ms", ui_refresh_est))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
