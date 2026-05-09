# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from openclaw_voice_stack.engines import create_asr_engine, create_tts_engine
from openclaw_voice_stack.engines.asr_dummy import DummyAsrEngine
from openclaw_voice_stack.engines.tts_espeak import EspeakTtsEngine


def test_dummy_asr_engine() -> None:
    engine = create_asr_engine("dummy", dummy_text="测试文本")
    assert isinstance(engine, DummyAsrEngine)
    assert engine.transcribe(b"", sample_rate=16000, language="zh-CN") == "测试文本"


def test_espeak_engine_factory() -> None:
    engine = create_tts_engine("espeak", voice="zh", speed=160, command="/bin/echo")
    assert isinstance(engine, EspeakTtsEngine)
