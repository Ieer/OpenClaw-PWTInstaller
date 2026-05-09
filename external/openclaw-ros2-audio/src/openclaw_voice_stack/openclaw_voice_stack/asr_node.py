# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from .audio_capture import AudioCaptureError, record_wav_bytes
from .engines import create_asr_engine


class AsrNode(Node):
    def __init__(self) -> None:
        super().__init__("asr_node")
        self.declare_parameter("wake_topic", "wakeup")
        self.declare_parameter("asr_topic", "asr")
        self.declare_parameter("asr_engine", "dummy")
        self.declare_parameter("dummy_text", "指挥 帮我建个任务给 health：检查今晚备份状态")
        self.declare_parameter("language", "zh-CN")
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("channels", 1)
        self.declare_parameter("max_utterance_seconds", 5.0)
        self.declare_parameter("wakeup_record_delay_ms", 0)
        self.declare_parameter("mic_device", os.getenv("OPENCLAW_AUDIO_INPUT_DEVICE", ""))
        self.declare_parameter("model_path", "")
        self.declare_parameter("asr_http_url_env", "OPENCLAW_ASR_HTTP_URL")
        self.declare_parameter("asr_http_token_env", "OPENCLAW_ASR_HTTP_TOKEN")

        self.wake_topic = str(self.get_parameter("wake_topic").value or "wakeup")
        self.asr_topic = str(self.get_parameter("asr_topic").value or "asr")
        self.engine_name = str(self.get_parameter("asr_engine").value or "dummy")
        self.language = str(self.get_parameter("language").value or "zh-CN")
        self.sample_rate = int(self.get_parameter("sample_rate").value)
        self.channels = int(self.get_parameter("channels").value)
        self.max_utterance_seconds = float(self.get_parameter("max_utterance_seconds").value)
        self.wakeup_record_delay_ms = int(self.get_parameter("wakeup_record_delay_ms").value)
        self.mic_device = str(self.get_parameter("mic_device").value or os.getenv("OPENCLAW_AUDIO_INPUT_DEVICE", ""))
        self.model_path = str(self.get_parameter("model_path").value or "")
        self.http_url_env = str(self.get_parameter("asr_http_url_env").value or "OPENCLAW_ASR_HTTP_URL")
        self.http_token_env = str(self.get_parameter("asr_http_token_env").value or "OPENCLAW_ASR_HTTP_TOKEN")
        self.dummy_text = str(self.get_parameter("dummy_text").value or "")

        self.publisher = self.create_publisher(String, self.asr_topic, 10)
        self.subscription = self.create_subscription(Bool, self.wake_topic, self._on_wakeup, 10)
        self._busy = threading.Event()
        self.engine = create_asr_engine(
            self.engine_name,
            dummy_text=self.dummy_text,
            url=os.getenv(self.http_url_env, ""),
            token=os.getenv(self.http_token_env, ""),
            language=self.language,
            model_path=self.model_path,
        )
        self.get_logger().info(f"asr_node ready engine={self.engine_name} wake_topic={self.wake_topic} asr_topic={self.asr_topic}")

    def _on_wakeup(self, msg: Bool) -> None:
        if not bool(msg.data):
            return
        if self._busy.is_set():
            self.get_logger().warning("ASR is already busy; ignoring wakeup")
            return
        self._busy.set()
        threading.Thread(target=self._record_and_transcribe, name="openclaw-asr-worker", daemon=True).start()

    def _record_and_transcribe(self) -> None:
        try:
            if self.engine_name.strip().lower() == "dummy":
                wav_bytes = b""
            else:
                delay_ms = max(0, self.wakeup_record_delay_ms)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                self.get_logger().info(
                    f"recording utterance seconds={self.max_utterance_seconds} sample_rate={self.sample_rate} device={self.mic_device or '<default>'}"
                )
                wav_bytes = record_wav_bytes(
                    seconds=self.max_utterance_seconds,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    device=self.mic_device,
                )
            text = self.engine.transcribe(wav_bytes, sample_rate=self.sample_rate, language=self.language).strip()
            if not text:
                self.get_logger().warning("ASR returned empty text; nothing published")
                return
            msg = String()
            msg.data = text
            self.publisher.publish(msg)
            self.get_logger().info(f"published ASR final text length={len(text)} topic={self.asr_topic}")
        except AudioCaptureError as exc:
            self.get_logger().error(f"audio capture failed: {exc}")
        except Exception as exc:
            self.get_logger().error(f"ASR failed: {exc}")
        finally:
            self._busy.clear()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = AsrNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
