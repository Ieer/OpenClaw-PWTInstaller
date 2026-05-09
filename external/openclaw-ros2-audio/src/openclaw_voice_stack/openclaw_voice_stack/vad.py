from __future__ import annotations

import audioop
import wave
from io import BytesIO


def pcm16_rms(pcm: bytes, width: int = 2) -> float:
    if not pcm:
        return 0.0
    return float(audioop.rms(pcm, width))


def wav_rms(wav_bytes: bytes) -> float:
    if not wav_bytes:
        return 0.0
    with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
        frames = wav_file.readframes(wav_file.getnframes())
        width = wav_file.getsampwidth() or 2
    return pcm16_rms(frames, width)


def has_voice(wav_bytes: bytes, *, threshold: float) -> bool:
    return wav_rms(wav_bytes) >= float(threshold)
