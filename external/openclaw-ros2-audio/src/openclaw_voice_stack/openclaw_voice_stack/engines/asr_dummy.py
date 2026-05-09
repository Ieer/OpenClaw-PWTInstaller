from __future__ import annotations

import os

from .asr_base import AsrEngine


class DummyAsrEngine(AsrEngine):
    def __init__(self, text: str = "") -> None:
        self.text = text or os.getenv("OPENCLAW_DUMMY_ASR_TEXT") or "指挥 帮我建个任务给 health：检查今晚备份状态"

    def transcribe(self, wav_bytes: bytes, *, sample_rate: int, language: str) -> str:
        return self.text.strip()
