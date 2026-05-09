# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .engines import create_tts_engine


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

        self.tts_request_topic = str(self.get_parameter("tts_request_topic").value or "tts_request")
        self.tts_topic = str(self.get_parameter("tts_topic").value or "tts_topic")
        self.engine_name = str(self.get_parameter("tts_engine").value or "espeak")
        self.voice = str(self.get_parameter("voice").value or os.getenv("OPENCLAW_TTS_VOICE", "zh"))
        self.output_device = str(self.get_parameter("output_device").value or os.getenv("OPENCLAW_AUDIO_OUTPUT_DEVICE", ""))
        self.speed = int(self.get_parameter("speed").value)
        self.model_path = str(self.get_parameter("model_path").value or "")
        self.command = str(self.get_parameter("command").value or "")

        self.status_publisher = self.create_publisher(String, self.tts_topic, 10)
        self.subscription = self.create_subscription(String, self.tts_request_topic, self._on_tts_request, 10)
        self.engine = create_tts_engine(
            self.engine_name,
            voice=self.voice,
            output_device=self.output_device,
            speed=self.speed,
            model_path=self.model_path,
            command=self.command,
        )
        self.get_logger().info(
            f"tts_node ready engine={self.engine_name} request_topic={self.tts_request_topic} status_topic={self.tts_topic}"
        )

    def _on_tts_request(self, msg: String) -> None:
        text = str(msg.data or "").strip()
        if not text:
            return
        status = String()
        status.data = text[:200]
        self.status_publisher.publish(status)
        self.get_logger().info(f"published TTS start status topic={self.tts_topic} length={len(text)}")
        threading.Thread(target=self._speak, args=(text,), name="openclaw-tts-worker", daemon=True).start()

    def _speak(self, text: str) -> None:
        try:
            self.engine.speak(text)
        except Exception as exc:
            self.get_logger().error(f"TTS failed: {exc}")


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
