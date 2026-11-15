from __future__ import annotations

import shutil
import subprocess
import threading

from .tts_base import TtsEngine, wait_process


class PiperTtsEngine(TtsEngine):
    def __init__(self, *, model_path: str) -> None:
        self.model_path = model_path.strip()

    def speak(self, text: str, cancel_event: threading.Event | None = None) -> None:
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
            stderr=subprocess.DEVNULL,
            text=False,
        )
        player_proc = None
        try:
            assert piper_proc.stdin is not None
            assert piper_proc.stdout is not None
            piper_proc.stdin.write(clean.encode("utf-8"))
            piper_proc.stdin.close()
            player_proc = subprocess.Popen(
                [aplay, "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
                stdin=piper_proc.stdout,
                stderr=subprocess.DEVNULL,
            )
            piper_proc.stdout.close()
            wait_process(player_proc, timeout=120, cancel_event=cancel_event)
            wait_process(piper_proc, timeout=5, cancel_event=cancel_event)
        except Exception:
            for process in (player_proc, piper_proc):
                if process is not None and process.poll() is None:
                    process.terminate()
            for process in (player_proc, piper_proc):
                if process is not None and process.poll() is None:
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            raise
