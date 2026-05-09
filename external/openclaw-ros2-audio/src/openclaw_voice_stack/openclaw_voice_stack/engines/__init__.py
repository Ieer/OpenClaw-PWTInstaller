from __future__ import annotations

from .asr_base import AsrEngine
from .asr_dummy import DummyAsrEngine
from .asr_http import HttpAsrEngine
from .asr_vosk import VoskAsrEngine
from .tts_base import TtsEngine
from .tts_edge import EdgeTtsEngine
from .tts_espeak import EspeakTtsEngine
from .tts_piper import PiperTtsEngine


def create_asr_engine(name: str, **kwargs) -> AsrEngine:
    normalized = (name or "dummy").strip().lower()
    if normalized == "dummy":
        return DummyAsrEngine(text=str(kwargs.get("dummy_text") or ""))
    if normalized == "http":
        return HttpAsrEngine(
            url=str(kwargs.get("url") or ""),
            token=str(kwargs.get("token") or ""),
            language=str(kwargs.get("language") or "zh-CN"),
        )
    if normalized == "vosk":
        return VoskAsrEngine(model_path=str(kwargs.get("model_path") or ""))
    raise ValueError(f"unsupported ASR engine: {name}")


def create_tts_engine(name: str, **kwargs) -> TtsEngine:
    normalized = (name or "espeak").strip().lower()
    if normalized == "espeak":
        return EspeakTtsEngine(
            voice=str(kwargs.get("voice") or "zh"),
            speed=int(kwargs.get("speed") or 165),
            command=str(kwargs.get("command") or ""),
        )
    if normalized == "edge":
        return EdgeTtsEngine(
            voice=str(kwargs.get("voice") or "zh-CN-XiaoxiaoNeural"),
            output_device=str(kwargs.get("output_device") or ""),
        )
    if normalized == "piper":
        return PiperTtsEngine(model_path=str(kwargs.get("model_path") or ""))
    raise ValueError(f"unsupported TTS engine: {name}")
