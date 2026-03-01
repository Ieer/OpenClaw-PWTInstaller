#!/usr/bin/env python3
import argparse
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import requests


TRIGGER_TYPES = {
    "chat.message.sent": "thinking",
    "chat.message.received": "speaking",
    "chat.proxy.error": "error",
}


@dataclass
class SentRecord:
    round_idx: int
    event_type: str
    expected_state: str
    sent_at_ms: float
    event_id: str


@dataclass
class SeenRecord:
    round_idx: int
    event_type: str
    received_at_ms: float
    event_id: str


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * p
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    return values_sorted[f] * (c - k) + values_sorted[c] * (k - f)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Overlay smoke test: 20 rounds event trigger + latency stats")
    parser.add_argument("--api-url", default=os.getenv("MISSION_CONTROL_API_URL", "http://127.0.0.1:18910"))
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--agent", default="nox")
    parser.add_argument("--ui-tick-ms", type=int, default=1000)
    parser.add_argument("--gap-ms", type=int, default=120)
    parser.add_argument("--timeout-s", type=int, default=25)
    parser.add_argument("--token", default=(os.getenv("MISSION_CONTROL_AUTH_TOKEN") or os.getenv("MC_AUTH_TOKEN") or "").strip())
    args = parser.parse_args()

    test_id = f"overlay-test-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    api_url = args.api_url.rstrip("/")

    print(f"[info] test_id={test_id}")
    print(f"[info] api={api_url}")

    sent_records: Dict[Tuple[int, str], SentRecord] = {}
    seen_records: Dict[Tuple[int, str], SeenRecord] = {}
    duplicate_events = 0
    unexpected_trigger_events = 0

    session = requests.Session()
    request_headers = {"Content-Type": "application/json"}
    if args.token:
        request_headers["Authorization"] = f"Bearer {args.token}"

    trigger_sequence = [
        ("chat.message.sent", {"method": "POST", "path": "/chat"}),
        ("chat.message.received", {"status_code": 200}),
        ("chat.proxy.error", {"error_type": "UpstreamTimeout"}),
    ]

    print(f"[info] injecting rounds={args.rounds} ...")
    for i in range(1, args.rounds + 1):
        # Optional noise event to estimate false-trigger proxy
        noise_payload = {
            "test_id": test_id,
            "round": i,
            "phase": "noise",
            "client_sent_at": iso_now(),
        }
        session.post(
            f"{api_url}/v1/events",
            headers=request_headers,
            json={
                "type": "task.updated",
                "agent": args.agent,
                "payload": noise_payload,
            },
            timeout=5,
        )

        for event_type, ext in trigger_sequence:
            now_ms = time.time() * 1000.0
            payload = {
                "test_id": test_id,
                "round": i,
                "phase": event_type,
                "client_sent_at": iso_now(),
                "client_sent_ms": now_ms,
                **ext,
            }
            resp = session.post(
                f"{api_url}/v1/events",
                headers=request_headers,
                json={
                    "type": event_type,
                    "agent": args.agent,
                    "payload": payload,
                },
                timeout=5,
            )
            resp.raise_for_status()
            body = resp.json()
            event_id = str(body.get("id") or "")
            sent_records[(i, event_type)] = SentRecord(
                round_idx=i,
                event_type=event_type,
                expected_state=TRIGGER_TYPES[event_type],
                sent_at_ms=now_ms,
                event_id=event_id,
            )
            time.sleep(max(0.01, args.gap_ms / 1000.0))

    expected = args.rounds * len(trigger_sequence)
    deadline = time.time() + args.timeout_s
    seen_by_id: Dict[str, float] = {}

    while time.time() < deadline and len(seen_by_id) < expected:
        try:
            feed = session.get(f"{api_url}/v1/feed?limit=250", headers=request_headers, timeout=5).json()
        except Exception:
            time.sleep(0.15)
            continue

        now_ms = time.time() * 1000.0
        for item in feed if isinstance(feed, list) else []:
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if str(payload.get("test_id") or "") != test_id:
                continue
            event_type = str(item.get("type") or "")
            event_id = str(item.get("id") or "")
            round_idx = int(payload.get("round") or -1)

            if event_type not in TRIGGER_TYPES:
                continue

            key = (round_idx, event_type)
            if key not in sent_records:
                unexpected_trigger_events += 1
                continue

            if not event_id:
                continue
            if event_id in seen_by_id:
                duplicate_events += 1
                continue

            seen_by_id[event_id] = now_ms
            sent = sent_records[key]
            if key not in seen_records:
                seen_records[key] = SeenRecord(
                    round_idx=round_idx,
                    event_type=event_type,
                    received_at_ms=now_ms,
                    event_id=event_id,
                )

        time.sleep(0.12)

    feed_latencies: List[float] = []
    visible_latencies_est: List[float] = []
    missing = 0

    for key, sent in sent_records.items():
        seen = seen_records.get(key)
        if not seen:
            missing += 1
            continue
        feed_latency = max(0.0, seen.received_at_ms - sent.sent_at_ms)
        feed_latencies.append(feed_latency)
        visible_latencies_est.append(feed_latency + float(args.ui_tick_ms) + 120.0)

    total_sent = len(sent_records)
    received = len(feed_latencies)
    false_trigger_proxy = (unexpected_trigger_events + duplicate_events)
    false_trigger_rate = (false_trigger_proxy / total_sent * 100.0) if total_sent else 0.0

    print("\n=== Overlay 20R Test Report ===")
    print(f"test_id: {test_id}")
    print(f"rounds: {args.rounds}")
    print(f"trigger_events_sent: {total_sent}")
    print(f"trigger_events_received: {received}")
    print(f"missing_events: {missing}")

    if feed_latencies:
        print("\n[feed_visibility_latency_ms]")
        print(f"p50={percentile(feed_latencies, 0.50):.1f} p95={percentile(feed_latencies, 0.95):.1f} p99={percentile(feed_latencies, 0.99):.1f} max={max(feed_latencies):.1f}")

        print("\n[visible_latency_est_ms]  # feed_visibility + ui_tick + render_margin")
        print(f"p50={percentile(visible_latencies_est, 0.50):.1f} p95={percentile(visible_latencies_est, 0.95):.1f} p99={percentile(visible_latencies_est, 0.99):.1f} max={max(visible_latencies_est):.1f}")
    else:
        print("\n[warn] no feed visibility samples captured")

    print("\n[false_trigger_proxy]")
    print(f"unexpected_trigger_events={unexpected_trigger_events}")
    print(f"duplicate_trigger_events={duplicate_events}")
    print(f"false_trigger_proxy_rate={false_trigger_rate:.2f}%")

    print("\n[note]")
    print("- visible_latency_est_ms is a proxy estimate based on feed-visibility + UI tick interval.")
    print("- For true on-screen latency, combine this with browser-side timestamp instrumentation.")

    return 0 if missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
