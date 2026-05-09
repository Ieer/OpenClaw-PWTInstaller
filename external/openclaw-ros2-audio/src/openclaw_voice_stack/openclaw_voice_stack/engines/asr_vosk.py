from __future__ import annotations

import json
import wave
from io import BytesIO

from .asr_base import AsrEngine


class VoskAsrEngine(AsrEngine):
    def __init__(self, *, model_path: str) -> None:
        self.model_path = model_path.strip()
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self.model_path:
            raise RuntimeError("Vosk model_path is required")
        try:
            from vosk import KaldiRecognizer, Model  # type: ignore
        except ImportError as exc:
            raise RuntimeError("vosk is not installed; install it before using asr.engine=vosk") from exc
        self._model = (Model(self.model_path), KaldiRecognizer)
        return self._model

    def transcribe(self, wav_bytes: bytes, *, sample_rate: int, language: str) -> str:
        model, recognizer_cls = self._load_model()
        with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
            recognizer = recognizer_cls(model, wav_file.getframerate() or sample_rate)
            while True:
                data = wav_file.readframes(4000)
                if not data:
                    break
                recognizer.AcceptWaveform(data)
            result = json.loads(recognizer.FinalResult() or "{}")
        return str(result.get("text") or "").strip()
