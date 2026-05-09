from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass


class AudioCaptureError(RuntimeError):
    """Raised when the local audio capture backend cannot record audio."""


@dataclass(slots=True)
class AudioDeviceReport:
    backend: str
    output: str


def list_audio_devices() -> list[AudioDeviceReport]:
    reports: list[AudioDeviceReport] = []
    for command in (["arecord", "-l"], ["aplay", "-l"], ["pactl", "list", "short", "sources"], ["pactl", "list", "short", "sinks"]):
        binary = command[0]
        if shutil.which(binary) is None:
            continue
        try:
            proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
        except Exception as exc:  # pragma: no cover - host dependent
            reports.append(AudioDeviceReport(binary, f"ERROR: {exc}"))
            continue
        text = (proc.stdout or proc.stderr or "").strip()
        reports.append(AudioDeviceReport(" ".join(command), text or "<no output>"))
    return reports


def record_wav_bytes(
    *,
    seconds: float,
    sample_rate: int = 16000,
    channels: int = 1,
    device: str = "",
) -> bytes:
    """Record a fixed-duration WAV clip with ALSA `arecord`.

    The MVP intentionally uses `arecord` before adding heavier Python audio
    dependencies. It works well on Raspberry Pi OS when ALSA can see the mic.
    """

    if shutil.which("arecord") is None:
        raise AudioCaptureError("arecord not found; install alsa-utils or provide another capture backend")

    duration = max(1, int(math.ceil(seconds)))
    command = [
        "arecord",
        "-q",
        "-f",
        "S16_LE",
        "-r",
        str(int(sample_rate)),
        "-c",
        str(int(channels)),
        "-d",
        str(duration),
        "-t",
        "wav",
    ]
    if device:
        command.extend(["-D", device])

    proc = subprocess.run(command, check=False, capture_output=True, timeout=duration + 5)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="ignore").strip()
        raise AudioCaptureError(stderr or f"arecord failed with exit code {proc.returncode}")
    if not proc.stdout:
        raise AudioCaptureError("arecord produced no audio bytes")
    return proc.stdout
