#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import json
import os
import queue
import random
import signal
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

try:
    rclpy = importlib.import_module("rclpy")
    Node = importlib.import_module("rclpy.node").Node
    _std_msgs = importlib.import_module("std_msgs.msg")
    Bool = _std_msgs.Bool
    String = _std_msgs.String
except Exception:
    rclpy = None
    Node = object
    Bool = object
    String = object


def _env_bool(name: str, default: bool) -> bool:
    value = (os.getenv(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class PendingEvent:
    event: dict[str, Any]
    event_key: str
    first_enqueued_at: float
    attempts: int = 0


class MissionControlEventSink:
    def __init__(self) -> None:
        api_base = (os.getenv("MC_API_URL") or "http://127.0.0.1:18910").rstrip("/")
        self.url = f"{api_base}/v1/events"
        self.token = (os.getenv("MC_AUTH_TOKEN") or "").strip()
        self.max_queue_size = max(100, _env_int("MC_VOICE_BRIDGE_QUEUE_SIZE", 2000))
        self.max_attempts = max(1, _env_int("MC_VOICE_BRIDGE_MAX_ATTEMPTS", 8))
        self.max_event_age_s = max(5.0, _env_float("MC_VOICE_BRIDGE_MAX_EVENT_AGE_S", 120.0))
        self.backoff_base_s = max(0.05, _env_float("MC_VOICE_BRIDGE_BACKOFF_BASE_S", 0.2))
        self.backoff_cap_s = max(self.backoff_base_s, _env_float("MC_VOICE_BRIDGE_BACKOFF_CAP_S", 5.0))
        self.log_payload = _env_bool("MC_VOICE_BRIDGE_LOG_PAYLOAD", False)

        self._queue: queue.Queue[PendingEvent] = queue.Queue(maxsize=self.max_queue_size)
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="mc-voice-bridge-sender", daemon=True)
        self._sent_cache: dict[str, float] = {}
        self._cache_ttl_s = max(30.0, _env_float("MC_VOICE_BRIDGE_EVENTKEY_TTL_S", 600.0))
        self._cache_max = max(500, _env_int("MC_VOICE_BRIDGE_EVENTKEY_MAX", 10000))
        self._lock = threading.Lock()

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        self._worker.join(timeout=2.0)

    def submit(self, event: dict[str, Any], event_key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._evict_cache_locked(now)
            if event_key in self._sent_cache:
                return
        pending = PendingEvent(event=event, event_key=event_key, first_enqueued_at=now)
        try:
            self._queue.put_nowait(pending)
        except queue.Full:
            print("[mc-voice-bridge] queue full, dropping event", flush=True)

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                pending = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            age_s = time.monotonic() - pending.first_enqueued_at
            if age_s > self.max_event_age_s:
                print(f"[mc-voice-bridge] drop stale event key={pending.event_key} age={age_s:.2f}s", flush=True)
                continue

            ok, status, retriable = self._post_json(pending.event)
            if ok:
                with self._lock:
                    self._sent_cache[pending.event_key] = time.monotonic()
                if self.log_payload:
                    print(f"[mc-voice-bridge] sent {json.dumps(pending.event, ensure_ascii=False)}", flush=True)
                continue

            pending.attempts += 1
            if not retriable or pending.attempts >= self.max_attempts:
                print(
                    f"[mc-voice-bridge] drop event key={pending.event_key} status={status} attempts={pending.attempts}",
                    flush=True,
                )
                continue

            sleep_s = min(self.backoff_cap_s, self.backoff_base_s * (2 ** max(0, pending.attempts - 1)))
            sleep_s = sleep_s * (0.85 + 0.3 * random.random())
            time.sleep(sleep_s)
            try:
                self._queue.put_nowait(pending)
            except queue.Full:
                print("[mc-voice-bridge] queue full during retry, dropping event", flush=True)

    def _post_json(self, payload: dict[str, Any]) -> tuple[bool, int, bool]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=2.5) as resp:
                status = int(getattr(resp, "status", 0) or 0)
            return 200 <= status < 300, status, False
        except error.HTTPError as exc:
            status = int(getattr(exc, "code", 0) or 0)
            retriable = status in {408, 425, 429, 500, 502, 503, 504}
            return False, status, retriable
        except Exception:
            return False, 0, True

    def _evict_cache_locked(self, now: float) -> None:
        expired = [key for key, ts in self._sent_cache.items() if now - ts > self._cache_ttl_s]
        for key in expired:
            self._sent_cache.pop(key, None)
        if len(self._sent_cache) <= self._cache_max:
            return
        items = sorted(self._sent_cache.items(), key=lambda kv: kv[1])
        for key, _ in items[: len(self._sent_cache) - self._cache_max]:
            self._sent_cache.pop(key, None)


class VoiceRosEventBridge(Node):
    def __init__(self) -> None:
        super().__init__("voice_ros_event_bridge")

        self.agent = (os.getenv("MC_VOICE_AGENT") or "voice-engine").strip() or "voice-engine"
        self.topic_wakeup = (os.getenv("MC_VOICE_TOPIC_WAKEUP") or "wakeup").strip() or "wakeup"
        self.topic_asr = (os.getenv("MC_VOICE_TOPIC_ASR") or "asr").strip() or "asr"
        self.topic_text_response = (os.getenv("MC_VOICE_TOPIC_TEXT_RESPONSE") or "text_response").strip() or "text_response"
        self.topic_tts = (os.getenv("MC_VOICE_TOPIC_TTS") or "tts_topic").strip() or "tts_topic"
        self.enable_llm_first_token = _env_bool("MC_VOICE_ENABLE_LLM_FIRST_TOKEN", True)
        self.idle_after_tts_s = max(1.0, _env_float("MC_VOICE_IDLE_AFTER_TTS_S", 6.0))

        self.current_turn_id = ""
        self.seq = 0
        self.has_llm_first_token = False
        self.speaking_since_mono = 0.0

        self.sink = MissionControlEventSink()
        self.sink.start()

        self.create_subscription(Bool, self.topic_wakeup, self._on_wakeup, 20)
        self.create_subscription(String, self.topic_asr, self._on_asr, 20)
        self.create_subscription(String, self.topic_text_response, self._on_text_response, 20)
        self.create_subscription(String, self.topic_tts, self._on_tts_start, 20)
        self.create_timer(0.25, self._on_tick)

        self.get_logger().info(
            f"voice bridge started agent={self.agent} topics="
            f"{self.topic_wakeup},{self.topic_asr},{self.topic_text_response},{self.topic_tts}"
        )

    def destroy_node(self) -> bool:
        try:
            self.sink.stop()
        finally:
            return super().destroy_node()

    def _next_turn(self) -> None:
        self.current_turn_id = hashlib.sha1(f"{self.agent}-{time.time_ns()}".encode("utf-8")).hexdigest()[:20]
        self.seq = 0
        self.has_llm_first_token = False
        self.speaking_since_mono = 0.0

    def _event_key(self, event_type: str, seq: int, text_fingerprint: str = "") -> str:
        base = f"{self.agent}|{self.current_turn_id}|{event_type}|{seq}|{text_fingerprint}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    def _emit(self, event_type: str, source_topic: str, payload: dict[str, Any] | None = None) -> None:
        if not self.current_turn_id:
            self._next_turn()
        self.seq += 1
        now_ms = int(time.time() * 1000)
        body = dict(payload or {})
        body["turn_id"] = self.current_turn_id
        body["seq"] = self.seq
        body["source_topic"] = source_topic
        body["client_sent_ms"] = now_ms
        body.setdefault("trace_id", self.current_turn_id)

        fp = ""
        if body.get("text"):
            fp = hashlib.sha1(str(body.get("text")).encode("utf-8")).hexdigest()[:8]
        elif body.get("state"):
            fp = str(body.get("state"))

        event_key = self._event_key(event_type, self.seq, fp)
        body["event_key"] = event_key

        event = {
            "type": event_type,
            "agent": self.agent,
            "payload": body,
        }
        self.sink.submit(event, event_key)

    def _safe_callback(self, fn_name: str, source_topic: str, cb) -> None:
        try:
            cb()
        except Exception as exc:
            self.get_logger().error(f"callback failed fn={fn_name}: {exc}")
            self._emit(
                "voice.error",
                source_topic,
                {
                    "error_type": "bridge_callback_error",
                    "error_message": str(exc)[:180],
                    "retryable": False,
                    "callback": fn_name,
                },
            )

    def _on_wakeup(self, msg: Any) -> None:
        def _cb() -> None:
            if not bool(msg.data):
                return
            self._next_turn()
            self._emit("voice.state", self.topic_wakeup, {"state": "listening", "trigger": "wakeup"})

        self._safe_callback("_on_wakeup", self.topic_wakeup, _cb)

    def _on_asr(self, msg: Any) -> None:
        def _cb() -> None:
            text = str(msg.data or "").strip()
            if not text:
                return
            if not self.current_turn_id:
                self._next_turn()
            self._emit("voice.asr.final", self.topic_asr, {"text": text})
            self._emit("voice.state", self.topic_asr, {"state": "thinking"})

        self._safe_callback("_on_asr", self.topic_asr, _cb)

    def _on_text_response(self, msg: Any) -> None:
        def _cb() -> None:
            if not self.enable_llm_first_token or self.has_llm_first_token:
                return
            text = str(msg.data or "").strip()
            if not text:
                return
            if not self.current_turn_id:
                self._next_turn()
            self._emit("voice.llm.first_token", self.topic_text_response, {"text": text[:120]})
            self.has_llm_first_token = True

        self._safe_callback("_on_text_response", self.topic_text_response, _cb)

    def _on_tts_start(self, msg: Any) -> None:
        def _cb() -> None:
            text = str(msg.data or "").strip()
            if not self.current_turn_id:
                self._next_turn()
            self._emit("voice.tts.start", self.topic_tts, {"text": text[:200] if text else ""})
            self._emit("voice.state", self.topic_tts, {"state": "speaking"})
            self.speaking_since_mono = time.monotonic()

        self._safe_callback("_on_tts_start", self.topic_tts, _cb)

    def _on_tick(self) -> None:
        if self.speaking_since_mono <= 0.0:
            return
        elapsed = time.monotonic() - self.speaking_since_mono
        if elapsed < self.idle_after_tts_s:
            return
        self._emit("voice.state", "bridge.timer", {"state": "idle"})
        self.speaking_since_mono = 0.0


def main() -> None:
    if rclpy is None:
        raise RuntimeError("ROS2 Python dependencies not found. Run inside a ROS2 Humble environment.")
    rclpy.init(args=None)
    node = VoiceRosEventBridge()
    stop_event = threading.Event()

    def _shutdown_handler(_sig, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    try:
        while rclpy.ok() and not stop_event.is_set():
            rclpy.spin_once(node, timeout_sec=0.2)
    finally:
        try:
            node.destroy_node()
        finally:
            rclpy.shutdown()


if __name__ == "__main__":
    main()
