from __future__ import annotations

from abc import ABC, abstractmethod


class AsrEngine(ABC):
    @abstractmethod
    def transcribe(self, wav_bytes: bytes, *, sample_rate: int, language: str) -> str:
        """Return final transcript text for a WAV clip."""
