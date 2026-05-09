# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os

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

        self.tts_request_topic = str(self.get_parameter("tts_request_topic").value or "tts_request")
        self.mc_api_url = str(self.get_parameter("mc_api_url").value or os.getenv("MC_API_URL", "http://127.0.0.1:18910"))
        self.mc_auth_token_env = str(self.get_parameter("mc_auth_token_env").value or "MC_AUTH_TOKEN")
        self.feed_limit = int(self.get_parameter("feed_limit").value)
        self.poll_interval_seconds = float(self.get_parameter("poll_interval_seconds").value)

        self.publisher = self.create_publisher(String, self.tts_request_topic, 10)
        self.client = MissionControlClient.from_env(api_url=self.mc_api_url, token_env=self.mc_auth_token_env)
        self.cursor = FeedCursor()
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
            msg.data = text
            self.publisher.publish(msg)
            self.get_logger().info(f"forwarded voice.tts.requested to {self.tts_request_topic} length={len(text)}")


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
