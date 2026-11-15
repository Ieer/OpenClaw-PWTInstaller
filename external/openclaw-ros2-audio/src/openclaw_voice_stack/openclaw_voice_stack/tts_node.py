# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os
import json
import queue
import threading
import uuid

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .engines import create_tts_engine
from .engines.tts_base import TtsCancelled


class TtsNode(Node):
    def __init__(self) -> None:
        super().__init__("tts_node")
        self.declare_parameter("tts_request_topic", "tts_request")
        self.declare_parameter("tts_topic", "tts_topic")
        self.declare_parameter("tts_engine", "espeak")
        self.declare_parameter("voice", os.getenv("OPENCLAW_TTS_VOICE", "zh"))
        self.declare_parameter("output_device", os.getenv("OPENCLAW_AUDIO_OUTPUT_DEVICE", ""))
        self.declare_parameter("speed", 165)
        self.declare_parameter("model_path", "")
        self.declare_parameter("command", "")
        self.declare_parameter("tts_cancel_topic", "tts_cancel")
        self.declare_parameter("queue_size", 16)

        self.tts_request_topic = str(self.get_parameter("tts_request_topic").value or "tts_request")
        self.tts_topic = str(self.get_parameter("tts_topic").value or "tts_topic")
        self.engine_name = str(self.get_parameter("tts_engine").value or "espeak")
        self.voice = str(self.get_parameter("voice").value or os.getenv("OPENCLAW_TTS_VOICE", "zh"))
        self.output_device = str(self.get_parameter("output_device").value or os.getenv("OPENCLAW_AUDIO_OUTPUT_DEVICE", ""))
        self.speed = int(self.get_parameter("speed").value)
        self.model_path = str(self.get_parameter("model_path").value or "")
        self.command = str(self.get_parameter("command").value or "")
        self.tts_cancel_topic = str(self.get_parameter("tts_cancel_topic").value or "tts_cancel")
        self.device_id = (os.getenv("MC_VOICE_DEVICE_ID") or "").strip()
        self.allow_untargeted = (os.getenv("MC_VOICE_ALLOW_UNTARGETED_TTS") or "").strip().lower() in {"1", "true", "yes", "on"}

        self.status_publisher = self.create_publisher(String, self.tts_topic, 10)
        self.subscription = self.create_subscription(String, self.tts_request_topic, self._on_tts_request, 10)
        self.cancel_subscription = self.create_subscription(String, self.tts_cancel_topic, self._on_tts_cancel, 10)
        self._queue = queue.Queue(maxsize=max(1, int(self.get_parameter("queue_size").value)))
        self._lock = threading.Lock()
        self._active_request_id = ""
        self._active_cancel = None
        self._queued_ids: set[str] = set()
        self._seen_request_ids: set[str] = set()
        self._request_order: list[str] = []
        self._cancelled_ids: set[str] = set()
        self._stop = threading.Event()
        self.engine = create_tts_engine(
            self.engine_name,
            voice=self.voice,
            output_device=self.output_device,
            speed=self.speed,
            model_path=self.model_path,
            command=self.command,
        )
        self._worker = threading.Thread(target=self._worker_loop, name="openclaw-tts-queue", daemon=True)
        self._worker.start()
        self.get_logger().info(
            f"tts_node ready engine={self.engine_name} request_topic={self.tts_request_topic} status_topic={self.tts_topic}"
        )

    @staticmethod
    def _request(raw: str) -> dict[str, str] | None:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            value = {"text": raw, "request_id": str(uuid.uuid4()), "device_id": ""}
        if not isinstance(value, dict):
            return None
        request_id = str(value.get("request_id") or "").strip()
        text = str(value.get("text") or "").strip()
        device_id = str(value.get("device_id") or "").strip()
        if not request_id or len(request_id) > 128 or not text or len(text) > 500:
            return None
        return {"request_id": request_id, "text": text, "device_id": device_id}

    def _publish_status(self, request: dict[str, str], status: str, error_type: str = "") -> None:
        value = {**request, "status": status}
        if error_type:
            value["error_type"] = error_type
        msg = String()
        msg.data = json.dumps(value, ensure_ascii=False)
        self.status_publisher.publish(msg)

    def _on_tts_request(self, msg: Any) -> None:
        request = self._request(str(msg.data or ""))
        if request is None:
            self.get_logger().warning("rejected malformed TTS request")
            return
        if (request["device_id"] and request["device_id"] != self.device_id) or (
                not request["device_id"] and not self.allow_untargeted):
            self._publish_status(request, "rejected", "device_mismatch")
            return
        with self._lock:
            if request["request_id"] in self._seen_request_ids:
                self._publish_status(request, "duplicate")
                return
            try:
                self._queue.put_nowait(request)
            except queue.Full:
                self._publish_status(request, "failed", "queue_full")
                return
            self._queued_ids.add(request["request_id"])
            self._seen_request_ids.add(request["request_id"])
            self._request_order.append(request["request_id"])
            while len(self._request_order) > 1000:
                self._seen_request_ids.discard(self._request_order.pop(0))
        self._publish_status(request, "queued")

    def _on_tts_cancel(self, msg: Any) -> None:
        raw = str(msg.data or "").strip()
        try:
            request_id = str(json.loads(raw).get("request_id") or "").strip()
        except (json.JSONDecodeError, AttributeError):
            request_id = raw
        if not request_id:
            return
        with self._lock:
            if request_id == self._active_request_id and self._active_cancel is not None:
                self._active_cancel.set()
            elif request_id in self._queued_ids:
                self._cancelled_ids.add(request_id)

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                request = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if request is None:
                return
            request_id = request["request_id"]
            cancel_event = threading.Event()
            with self._lock:
                self._queued_ids.discard(request_id)
                if request_id in self._cancelled_ids:
                    self._cancelled_ids.discard(request_id)
                    self._publish_status(request, "cancelled")
                    self._queue.task_done()
                    continue
                self._active_request_id = request_id
                self._active_cancel = cancel_event
            self._publish_status(request, "started")
            try:
                self.engine.speak(request["text"], cancel_event=cancel_event)
                status, error_type = "finished", ""
            except TtsCancelled:
                status, error_type = "cancelled", ""
            except Exception as exc:
                status, error_type = "failed", type(exc).__name__
                self.get_logger().error(f"TTS request failed request_id={request_id} error_type={error_type}")
            finally:
                with self._lock:
                    self._active_request_id = ""
                    self._active_cancel = None
                self._publish_status(request, status, error_type)
                self._queue.task_done()

    def destroy_node(self) -> bool:
        self._stop.set()
        with self._lock:
            if self._active_cancel is not None:
                self._active_cancel.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._worker.join(timeout=3)
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TtsNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
