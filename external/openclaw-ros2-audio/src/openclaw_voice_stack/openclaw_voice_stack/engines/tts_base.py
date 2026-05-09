from __future__ import annotations

from abc import ABC, abstractmethod


class TtsEngine(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak text or raise an exception on failure."""
