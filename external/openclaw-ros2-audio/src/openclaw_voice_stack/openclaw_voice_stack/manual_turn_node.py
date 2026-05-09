# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class ManualTurnNode(Node):
    def __init__(self) -> None:
        super().__init__("manual_turn_node")
        self.declare_parameter("wake_topic", "wakeup")
        self.declare_parameter("asr_topic", "asr")
        self.declare_parameter("text_response_topic", "text_response")
        self.declare_parameter("tts_topic", "tts_topic")
        self.declare_parameter("asr_text", "指挥 帮我建个任务给 health：检查今晚备份状态")
        self.declare_parameter("text_response", "processing manual turn")
        self.declare_parameter("tts_text", "manual turn speaking")
        self.declare_parameter("publish_text_response", False)
        self.declare_parameter("delay_seconds", 0.35)
        self.declare_parameter("wait_for_subscriptions", True)
        self.declare_parameter("subscription_wait_seconds", 5.0)

        self.wake_topic = str(self.get_parameter("wake_topic").value or "wakeup")
        self.asr_topic = str(self.get_parameter("asr_topic").value or "asr")
        self.text_response_topic = str(self.get_parameter("text_response_topic").value or "text_response")
        self.tts_topic = str(self.get_parameter("tts_topic").value or "tts_topic")
        self.asr_text = str(self.get_parameter("asr_text").value or "")
        self.text_response = str(self.get_parameter("text_response").value or "")
        self.tts_text = str(self.get_parameter("tts_text").value or "")
        self.publish_text_response = bool(self.get_parameter("publish_text_response").value)
        self.delay_seconds = float(self.get_parameter("delay_seconds").value)
        self.wait_for_subscriptions = bool(self.get_parameter("wait_for_subscriptions").value)
        self.subscription_wait_seconds = float(self.get_parameter("subscription_wait_seconds").value)

        self.wake_pub = self.create_publisher(Bool, self.wake_topic, 10)
        self.asr_pub = self.create_publisher(String, self.asr_topic, 10)
        self.text_response_pub = self.create_publisher(String, self.text_response_topic, 10)
        self.tts_pub = self.create_publisher(String, self.tts_topic, 10)

    def _wait_for_subscription(self, publisher, topic_name: str) -> None:
        if not self.wait_for_subscriptions:
            return
        deadline = time.monotonic() + max(0.0, self.subscription_wait_seconds)
        while rclpy.ok() and time.monotonic() < deadline:
            if publisher.get_subscription_count() > 0:
                return
            rclpy.spin_once(self, timeout_sec=0.1)
        self.get_logger().warning(f"no subscriber discovered for /{topic_name}; publishing anyway")

    def publish_turn(self) -> None:
        time.sleep(self.delay_seconds)
        self._wait_for_subscription(self.wake_pub, self.wake_topic)
        wake = Bool()
        wake.data = True
        self.wake_pub.publish(wake)
        self.get_logger().info(f"published /{self.wake_topic} true")
        time.sleep(self.delay_seconds)

        self._wait_for_subscription(self.asr_pub, self.asr_topic)
        asr = String()
        asr.data = self.asr_text
        self.asr_pub.publish(asr)
        self.get_logger().info(f"published /{self.asr_topic}: {self.asr_text}")
        time.sleep(self.delay_seconds)

        if self.publish_text_response and self.text_response:
            self._wait_for_subscription(self.text_response_pub, self.text_response_topic)
            response = String()
            response.data = self.text_response
            self.text_response_pub.publish(response)
            self.get_logger().info(f"published /{self.text_response_topic}: {self.text_response}")
            time.sleep(self.delay_seconds)

        if self.tts_text:
            self._wait_for_subscription(self.tts_pub, self.tts_topic)
            tts = String()
            tts.data = self.tts_text
            self.tts_pub.publish(tts)
            self.get_logger().info(f"published /{self.tts_topic}: {self.tts_text}")
            time.sleep(self.delay_seconds)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ManualTurnNode()
    try:
        node.publish_turn()
        rclpy.spin_once(node, timeout_sec=0.2)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
