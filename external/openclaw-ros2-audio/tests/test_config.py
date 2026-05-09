# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from openclaw_voice_stack.config import app_config_from_dict


def test_app_config_defaults() -> None:
    cfg = app_config_from_dict({})
    assert cfg.topics.wake == "wakeup"
    assert cfg.topics.asr == "asr"
    assert cfg.asr.engine == "dummy"
    assert cfg.tts.engine == "espeak"


def test_app_config_overrides() -> None:
    cfg = app_config_from_dict(
        {
            "topics": {"wake": "custom_wake", "tts_request": "say"},
            "audio": {"sample_rate": 8000, "max_utterance_seconds": 3.5},
            "asr": {"engine": "http", "language": "zh"},
            "tts": {"engine": "edge", "voice": "zh-CN-XiaoxiaoNeural"},
        }
    )
    assert cfg.topics.wake == "custom_wake"
    assert cfg.topics.tts_request == "say"
    assert cfg.audio.sample_rate == 8000
    assert cfg.audio.max_utterance_seconds == 3.5
    assert cfg.asr.engine == "http"
    assert cfg.tts.engine == "edge"
