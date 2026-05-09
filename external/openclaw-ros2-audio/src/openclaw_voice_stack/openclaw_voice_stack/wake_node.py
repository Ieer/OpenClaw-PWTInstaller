# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from .audio_capture import AudioCaptureError, record_wav_bytes
from .vad import has_voice


class WakeNode(Node):
    def __init__(self) -> None:
        super().__init__("wake_node")
        self.declare_parameter("wake_topic", "wakeup")
        self.declare_parameter("mode", "manual")
        self.declare_parameter("cooldown_ms", 1800)
        self.declare_parameter("energy_threshold", 1200.0)
        self.declare_parameter("mic_device", os.getenv("OPENCLAW_AUDIO_INPUT_DEVICE", ""))
        self.declare_parameter("energy_probe_seconds", 0.35)
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("channels", 1)

        self.wake_topic = str(self.get_parameter("wake_topic").value or "wakeup")
        self.mode = str(self.get_parameter("mode").value or "manual").strip().lower()
        self.cooldown_s = max(0.0, float(self.get_parameter("cooldown_ms").value) / 1000.0)
        self.energy_threshold = float(self.get_parameter("energy_threshold").value)
        self.mic_device = str(self.get_parameter("mic_device").value or os.getenv("OPENCLAW_AUDIO_INPUT_DEVICE", ""))
        self.energy_probe_seconds = float(self.get_parameter("energy_probe_seconds").value)
        self.sample_rate = int(self.get_parameter("sample_rate").value)
        self.channels = int(self.get_parameter("channels").value)

        self.publisher = self.create_publisher(Bool, self.wake_topic, 10)
        self._last_wake = 0.0
        self._stop_event = threading.Event()

        if self.mode in {"manual", "keyboard"}:
            self._stdin_thread = threading.Thread(target=self._stdin_loop, name="openclaw-wake-stdin", daemon=True)
            self._stdin_thread.start()
            self.get_logger().info("wake_node waiting for Enter/stdin trigger")
        elif self.mode == "energy_threshold":
            self.create_timer(max(0.2, self.energy_probe_seconds), self._energy_probe)
            self.get_logger().info(
                f"wake_node energy threshold mode threshold={self.energy_threshold} device={self.mic_device or '<default>'}"
            )
        else:
            self.get_logger().warning(f"unsupported wake mode '{self.mode}', falling back to manual stdin")
            self._stdin_thread = threading.Thread(target=self._stdin_loop, name="openclaw-wake-stdin", daemon=True)
            self._stdin_thread.start()

    def destroy_node(self) -> bool:
        self._stop_event.set()
        return super().destroy_node()

    def _publish_wake(self, *, source: str) -> None:
        now = time.monotonic()
        if now - self._last_wake < self.cooldown_s:
            return
        self._last_wake = now
        msg = Bool()
        msg.data = True
        self.publisher.publish(msg)
        self.get_logger().info(f"published wakeup true source={source} topic={self.wake_topic}")

    def _stdin_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                line = input("[wake_node] press Enter or type wake > ")
            except EOFError:
                self.get_logger().warning("stdin closed; manual wake trigger disabled")
                return
            if self._stop_event.is_set():
                return
            if not line.strip() or line.strip().lower() in {"wake", "w", "1", "true"}:
                self._publish_wake(source="stdin")

    def _energy_probe(self) -> None:
        try:
            wav_bytes = record_wav_bytes(
                seconds=self.energy_probe_seconds,
                sample_rate=self.sample_rate,
                channels=self.channels,
                device=self.mic_device,
            )
        except AudioCaptureError as exc:
            self.get_logger().warning(f"energy probe failed: {exc}")
            return
        except Exception as exc:
            self.get_logger().warning(f"energy probe unexpected error: {exc}")
            return
        if has_voice(wav_bytes, threshold=self.energy_threshold):
            self._publish_wake(source="energy_threshold")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = WakeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
