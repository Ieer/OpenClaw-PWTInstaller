from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("voice_ros_event_bridge.py")
SPEC = importlib.util.spec_from_file_location("voice_ros_event_bridge_tested", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load voice bridge module")
voice_bridge = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = voice_bridge
SPEC.loader.exec_module(voice_bridge)


class VoiceBridgeIdempotencyTests(unittest.TestCase):
    def test_stale_tts_completion_cannot_override_new_turn_state(self):
        class Message:
            data = json.dumps({"request_id": "old", "device_id": "desk", "status": "finished"})
        voice_bridge.String = Message
        node = object.__new__(voice_bridge.VoiceRosEventBridge)
        node.topic_tts = "tts_topic"
        node.device_id = "desk"
        node.current_turn_id = "new-turn"
        node.seq = 1
        node.has_llm_first_token = False
        node.speaking_since_mono = 0.0
        node.legacy_speaking = False
        node.active_tts_request_id = "new"
        node.sink = Mock()
        node.get_logger = Mock(return_value=Mock())

        node._on_tts_start(Message())

        node.sink.submit.assert_not_called()

    def test_new_turn_cancellation_targets_only_active_tts_request(self):
        class Message:
            data = ""
        voice_bridge.String = Message
        node = object.__new__(voice_bridge.VoiceRosEventBridge)
        node.active_tts_request_id = "tts-event-1"
        node.tts_cancel_publisher = Mock()
        node.speaking_since_mono = 10.0
        node.legacy_speaking = False

        node._cancel_active_tts()

        node.tts_cancel_publisher.publish.assert_called_once()
        self.assertEqual(json.loads(node.tts_cancel_publisher.publish.call_args.args[0].data),
                         {"request_id": "tts-event-1"})
        self.assertEqual(node.active_tts_request_id, "")

    def test_device_identity_is_attached_to_every_event(self):
        node = object.__new__(voice_bridge.VoiceRosEventBridge)
        node.agent = "voice-engine"
        node.device_id = "desk"
        node.current_turn_id = "turn-1"
        node.seq = 0
        node.has_llm_first_token = False
        node.speaking_since_mono = 0.0
        node.sink = Mock()

        node._emit("voice.asr.final", "asr", {"text": "synthetic"})

        event = node.sink.submit.call_args.args[0]
        self.assertEqual(event["payload"]["device_id"], "desk")

    def test_event_key_is_forwarded_as_idempotency_key_on_replay(self):
        sink = voice_bridge.MissionControlEventSink()
        payload = {"type": "voice.asr.final", "payload": {"event_key": "stable-event-123", "text": "synthetic"}}
        requests = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def capture(req, timeout):
            requests.append(req)
            return Response()

        with patch.object(voice_bridge.request, "urlopen", side_effect=capture):
            self.assertEqual(sink._post_json(payload), (True, 200, False))
            self.assertEqual(sink._post_json(payload), (True, 200, False))

        self.assertEqual([req.get_header("Idempotency-key") for req in requests], ["stable-event-123"] * 2)

    def test_missing_event_key_does_not_create_shared_idempotency_key(self):
        sink = voice_bridge.MissionControlEventSink()
        payload = {"type": "voice.state", "payload": {"state": "listening"}}
        requests = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with patch.object(voice_bridge.request, "urlopen", side_effect=lambda req, timeout: (requests.append(req) or Response())):
            self.assertEqual(sink._post_json(payload), (True, 200, False))

        self.assertIsNone(requests[0].get_header("Idempotency-key"))


if __name__ == "__main__":
    unittest.main()