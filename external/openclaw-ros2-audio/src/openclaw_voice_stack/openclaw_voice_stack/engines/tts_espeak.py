from __future__ import annotations

import shutil
import subprocess

from .tts_base import TtsEngine


class EspeakTtsEngine(TtsEngine):
    def __init__(self, *, voice: str = "zh", speed: int = 165, command: str = "") -> None:
        self.voice = voice
        self.speed = int(speed)
        self.command = command.strip() or shutil.which("espeak-ng") or shutil.which("espeak") or ""

    def speak(self, text: str) -> None:
        clean = text.strip()
        if not clean:
            return
        if not self.command:
            raise RuntimeError("espeak-ng/espeak not found; install espeak-ng or choose another TTS engine")
        subprocess.run(
            [self.command, "-v", self.voice, "-s", str(self.speed), clean],
            check=True,
            timeout=max(15, min(120, len(clean) // 3 + 15)),
        )
