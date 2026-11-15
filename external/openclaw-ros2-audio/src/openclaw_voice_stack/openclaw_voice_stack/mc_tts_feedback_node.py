# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os
import json
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .mission_control_client import FeedCursor, MissionControlClient, MissionControlClientError


class MissionControlTtsFeedbackNode(Node):
    def __init__(self) -> None:
        super().__init__("mc_tts_feedback_node")
        self.declare_parameter("tts_request_topic", "tts_request")
        self.declare_parameter("mc_api_url", os.getenv("MC_API_URL", "http://127.0.0.1:18910"))
        self.declare_parameter("mc_auth_token_env", "MC_AUTH_TOKEN")
        self.declare_parameter("feed_limit", 80)
        self.declare_parameter("poll_interval_seconds", 1.0)
        self.declare_parameter("tts_status_topic", os.getenv("MC_VOICE_TOPIC_TTS", "tts_topic"))

        self.tts_request_topic = str(self.get_parameter("tts_request_topic").value or "tts_request")
        self.mc_api_url = str(self.get_parameter("mc_api_url").value or os.getenv("MC_API_URL", "http://127.0.0.1:18910"))
        self.mc_auth_token_env = str(self.get_parameter("mc_auth_token_env").value or "MC_AUTH_TOKEN")
        self.feed_limit = int(self.get_parameter("feed_limit").value)
        self.poll_interval_seconds = float(self.get_parameter("poll_interval_seconds").value)
        self.tts_status_topic = str(self.get_parameter("tts_status_topic").value or "tts_topic")
        self.device_id = (os.getenv("MC_VOICE_DEVICE_ID") or "").strip()

        self.publisher = self.create_publisher(String, self.tts_request_topic, 10)
        self.status_subscription = self.create_subscription(String, self.tts_status_topic, self._on_tts_status, 10)
        self.client = MissionControlClient.from_env(api_url=self.mc_api_url, token_env=self.mc_auth_token_env)
        cursor_path = os.getenv("MC_VOICE_CURSOR_DB") or str(Path.home() / ".openclaw" / "voice" / "tts-cursor.sqlite3")
        self.cursor = FeedCursor(device_id=self.device_id, state_path=cursor_path)
        self.pending_events: dict[str, dict] = {}
        if not self.device_id:
            self.get_logger().warning("MC_VOICE_DEVICE_ID is empty; device-targeted TTS feedback is disabled")
        self.create_timer(max(0.2, self.poll_interval_seconds), self._poll_once)
        self.get_logger().info(f"mc_tts_feedback_node polling {self.mc_api_url} -> topic={self.tts_request_topic}")

    def _poll_once(self) -> None:
        try:
            feed = self.client.feed(limit=self.feed_limit)
        except MissionControlClientError as exc:
            self.get_logger().warning(f"Mission Control feed poll failed: {exc}")
            return
        except Exception as exc:
            self.get_logger().warning(f"Mission Control feed unexpected error: {exc}")
            return

        for event in self.cursor.filter_new_tts_requests(feed):
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            text = str(payload.get("text") or "").strip()
            if not text:
                continue
            msg = String()
            request_id = str(event.get("id") or self.cursor.event_key(event))
            self.pending_events[request_id] = event
            msg.data = json.dumps({
                "request_id": request_id,
                "device_id": self.device_id,
                "text": text[:500],
            }, ensure_ascii=False)
            self.publisher.publish(msg)
            self.get_logger().info(f"forwarded voice.tts.requested to {self.tts_request_topic} length={len(text)}")

    def _on_tts_status(self, msg) -> None:
        try:
            status = json.loads(str(msg.data or ""))
        except json.JSONDecodeError:
            return
        if not isinstance(status, dict) or status.get("status") not in {"finished", "failed", "cancelled", "rejected"}:
            return
        if str(status.get("device_id") or "") != self.device_id:
            return
        request_id = str(status.get("request_id") or "")
        if status.get("status") == "failed" and status.get("error_type") == "queue_full":
            event = self.pending_events.pop(request_id, None)
            if event is not None:
                self.cursor.release(event)
            return
        event = self.pending_events.pop(request_id, None)
        if event is not None:
            self.cursor.acknowledge(event)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = MissionControlTtsFeedbackNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
