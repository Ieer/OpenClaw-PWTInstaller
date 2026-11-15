from __future__ import annotations

import json
import queue
import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

node_module = types.ModuleType("rclpy.node")
node_module.Node = object
ros_module = types.ModuleType("rclpy")
ros_module.node = node_module
ros_module.init = lambda *args, **kwargs: None
message_module = types.ModuleType("std_msgs.msg")
message_module.String = type("RosString", (), {})
sys.modules.setdefault("rclpy", ros_module)
sys.modules.setdefault("rclpy.node", node_module)
sys.modules.setdefault("std_msgs", types.ModuleType("std_msgs"))
sys.modules.setdefault("std_msgs.msg", message_module)

from openclaw_voice_stack import tts_node
from openclaw_voice_stack.engines.tts_base import TtsCancelled


class StringMessage:
    def __init__(self):
        self.data = ""


tts_node.String = StringMessage


def make_node(*, device_id="desk"):
    node = object.__new__(tts_node.TtsNode)
    node.device_id = device_id
    node.allow_untargeted = False
    node._queue = queue.Queue(maxsize=4)
    node._lock = threading.Lock()
    node._active_request_id = ""
    node._active_cancel = None
    node._queued_ids = set()
    node._seen_request_ids = set()
    node._request_order = []
    node._cancelled_ids = set()
    node._stop = threading.Event()
    node.status_publisher = Mock()
    node.get_logger = Mock(return_value=Mock())
    return node


def request(request_id, device_id="desk", text="hello"):
    return SimpleNamespace(data=json.dumps({"request_id": request_id, "device_id": device_id, "text": text}))


def statuses(node):
    return [json.loads(call.args[0].data) for call in node.status_publisher.publish.call_args_list]


def test_tts_node_rejects_other_devices_and_untargeted_requests():
    node = make_node()
    node._on_tts_request(request("other", device_id="robot"))
    node._on_tts_request(SimpleNamespace(data=json.dumps({"request_id": "legacy", "text": "hello"})))
    assert node._queue.empty()
    assert [item["error_type"] for item in statuses(node)] == ["device_mismatch", "device_mismatch"]


def test_tts_node_deduplicates_queued_request_ids():
    node = make_node()
    node._on_tts_request(request("same"))
    node._on_tts_request(request("same"))
    assert node._queue.qsize() == 1
    assert [item["status"] for item in statuses(node)] == ["queued", "duplicate"]


def test_tts_node_serializes_and_cancels_active_playback():
    node = make_node()
    started = threading.Event()
    played = []

    class Engine:
        def speak(self, text, *, cancel_event):
            played.append((text, "started"))
            if text == "first":
                started.set()
                assert cancel_event.wait(2)
                played.append((text, "cancelled"))
                raise TtsCancelled("cancelled")
            played.append((text, "finished"))

    node.engine = Engine()
    worker = threading.Thread(target=node._worker_loop)
    worker.start()
    node._on_tts_request(request("first", text="first"))
    assert started.wait(2)
    node._on_tts_request(request("second", text="second"))
    node._on_tts_cancel(SimpleNamespace(data=json.dumps({"request_id": "first"})))
    assert node._queue.join() is None
    node._stop.set()
    worker.join(2)
    assert not worker.is_alive()
    assert played == [("first", "started"), ("first", "cancelled"), ("second", "started"), ("second", "finished")]
    transitions = [(item["request_id"], item["status"]) for item in statuses(node)]
    assert transitions == [("first", "queued"), ("first", "started"), ("second", "queued"),
                           ("first", "cancelled"), ("second", "started"), ("second", "finished")]
