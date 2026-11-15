from __future__ import annotations

import shutil
import threading
import tempfile
from pathlib import Path

from .tts_base import TtsEngine, run_process


class EdgeTtsEngine(TtsEngine):
    def __init__(self, *, voice: str = "zh-CN-XiaoxiaoNeural", output_device: str = "") -> None:
        self.voice = voice
        self.output_device = output_device

    def speak(self, text: str, cancel_event: threading.Event | None = None) -> None:
        clean = text.strip()
        if not clean:
            return
        edge_tts = shutil.which("edge-tts")
        if edge_tts is None:
            raise RuntimeError("edge-tts CLI not found; install edge-tts before using tts.engine=edge")
        player = shutil.which("mpg123") or shutil.which("ffplay")
        if player is None:
            raise RuntimeError("mpg123 or ffplay is required to play edge-tts output")
        with tempfile.TemporaryDirectory(prefix="openclaw-edge-tts-") as tmpdir:
            media_path = Path(tmpdir) / "speech.mp3"
            run_process([edge_tts, "--voice", self.voice, "--text", clean, "--write-media", str(media_path)],
                        timeout=120, cancel_event=cancel_event)
            if Path(player).name == "ffplay":
                run_process([player, "-nodisp", "-autoexit", "-loglevel", "error", str(media_path)],
                            timeout=120, cancel_event=cancel_event)
            else:
                player_args = [player, "-q"]
                if self.output_device:
                    player_args.extend(["-a", self.output_device])
                player_args.append(str(media_path))
                run_process(player_args, timeout=120, cancel_event=cancel_event)
