# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from openclaw_voice_stack.mission_control_client import FeedCursor


def test_feed_cursor_filters_new_tts_requests_once() -> None:
    cursor = FeedCursor()
    feed = [
        {"id": "1", "type": "voice.asr.final", "payload": {"text": "hello"}},
        {"id": "2", "type": "voice.tts.requested", "payload": {"text": "已创建任务"}},
    ]
    first = cursor.filter_new_tts_requests(feed)
    second = cursor.filter_new_tts_requests(feed)
    assert [item["id"] for item in first] == ["2"]
    assert second == []


def test_feed_cursor_fallback_key() -> None:
    cursor = FeedCursor()
    feed = [
        {"type": "voice.tts.requested", "created_at": "now", "payload": {"text": "播报", "event_key": "abc"}},
    ]
    assert len(cursor.filter_new_tts_requests(feed)) == 1
    assert cursor.filter_new_tts_requests(feed) == []
