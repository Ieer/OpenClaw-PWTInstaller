from __future__ import annotations

import shutil
import subprocess

from .tts_base import TtsEngine


class PiperTtsEngine(TtsEngine):
    def __init__(self, *, model_path: str) -> None:
        self.model_path = model_path.strip()

    def speak(self, text: str) -> None:
        clean = text.strip()
        if not clean:
            return
        piper = shutil.which("piper")
        aplay = shutil.which("aplay")
        if piper is None:
            raise RuntimeError("piper binary not found; install Piper before using tts.engine=piper")
        if aplay is None:
            raise RuntimeError("aplay not found; install alsa-utils before using tts.engine=piper")
        if not self.model_path:
            raise RuntimeError("Piper model_path is required")
        piper_proc = subprocess.Popen(
            [piper, "--model", self.model_path, "--output-raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        assert piper_proc.stdin is not None
        assert piper_proc.stdout is not None
        piper_proc.stdin.write(clean.encode("utf-8"))
        piper_proc.stdin.close()
        subprocess.run([aplay, "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"], stdin=piper_proc.stdout, check=True, timeout=120)
        piper_proc.wait(timeout=5)
        if piper_proc.returncode not in (0, None):
            stderr = (piper_proc.stderr.read() if piper_proc.stderr else b"").decode("utf-8", errors="ignore")
            raise RuntimeError(stderr or f"piper failed with exit code {piper_proc.returncode}")
