# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from pathlib import Path

from openclaw_voice_stack.mission_control_client import FeedCursor


def test_feed_cursor_filters_new_tts_requests_once(tmp_path: Path) -> None:
    cursor = FeedCursor(device_id="desk", state_path=tmp_path / "cursor.sqlite3")
    assert cursor.filter_new_tts_requests([]) == []
    feed = [
        {"id": "1", "type": "voice.asr.final", "payload": {"text": "hello"}},
        {"id": "2", "type": "voice.tts.requested", "payload": {"device_id": "desk", "text": "已创建任务"}},
    ]
    first = cursor.filter_new_tts_requests(feed)
    second = cursor.filter_new_tts_requests(feed)
    assert [item["id"] for item in first] == ["2"]
    assert second == []


def test_feed_cursor_fallback_key(tmp_path: Path) -> None:
    cursor = FeedCursor(device_id="desk", state_path=tmp_path / "cursor.sqlite3")
    assert cursor.filter_new_tts_requests([]) == []
    feed = [
        {"type": "voice.tts.requested", "created_at": "now", "payload": {"text": "播报", "event_key": "abc", "device_id": "desk"}},
    ]
    assert len(cursor.filter_new_tts_requests(feed)) == 1
    assert cursor.filter_new_tts_requests(feed) == []


def test_feed_cursor_isolates_devices_and_persists_consumed_events(tmp_path: Path) -> None:
    state_path = tmp_path / "private" / "cursor.sqlite3"
    feed = [
        {"id": "desk-1", "type": "voice.tts.requested", "payload": {"text": "desk", "device_id": "desk"}},
        {"id": "robot-1", "type": "voice.tts.requested", "payload": {"text": "robot", "device_id": "robot"}},
        {"id": "legacy-1", "type": "voice.tts.requested", "payload": {"text": "untargeted"}},
    ]

    first = FeedCursor(device_id="desk", state_path=state_path)
    assert first.filter_new_tts_requests(feed) == []
    new_event = {"id": "desk-2", "type": "voice.tts.requested", "payload": {"text": "new", "device_id": "desk"}}
    feed.append(new_event)
    assert [item["id"] for item in first.filter_new_tts_requests(feed)] == ["desk-2"]
    assert first.filter_new_tts_requests(feed) == []
    first.release(new_event)
    assert first.filter_new_tts_requests(feed) == [new_event]
    first.release(new_event)

    restarted = FeedCursor(device_id="desk", state_path=state_path)
    assert [item["id"] for item in restarted.filter_new_tts_requests(feed)] == ["desk-2"]
    first.acknowledge(new_event)
    acknowledged = FeedCursor(device_id="desk", state_path=state_path)
    assert acknowledged.filter_new_tts_requests(feed) == []

    robot_cursor = FeedCursor(device_id="robot", state_path=state_path)
    assert robot_cursor.filter_new_tts_requests(feed) == []
    robot_event = {"id": "robot-2", "type": "voice.tts.requested", "payload": {"text": "new", "device_id": "robot"}}
    assert robot_cursor.filter_new_tts_requests(feed + [robot_event]) == [robot_event]
    assert state_path.stat().st_mode & 0o777 == 0o600


def test_feed_cursor_bounds_unacknowledged_events(tmp_path: Path) -> None:
    cursor = FeedCursor(device_id="desk", state_path=tmp_path / "cursor.sqlite3", max_pending=2)
    assert cursor.filter_new_tts_requests([]) == []
    feed = [
        {"id": f"event-{index}", "type": "voice.tts.requested", "payload": {"text": str(index), "device_id": "desk"}}
        for index in range(5)
    ]
    assert len(cursor.filter_new_tts_requests(feed)) == 2
    assert len(cursor.pending_keys) == 2
