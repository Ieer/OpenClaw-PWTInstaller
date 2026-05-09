from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .tts_base import TtsEngine


class EdgeTtsEngine(TtsEngine):
    def __init__(self, *, voice: str = "zh-CN-XiaoxiaoNeural", output_device: str = "") -> None:
        self.voice = voice
        self.output_device = output_device

    def speak(self, text: str) -> None:
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
            subprocess.run([edge_tts, "--voice", self.voice, "--text", clean, "--write-media", str(media_path)], check=True, timeout=120)
            if Path(player).name == "ffplay":
                subprocess.run([player, "-nodisp", "-autoexit", "-loglevel", "error", str(media_path)], check=True, timeout=120)
            else:
                player_args = [player, "-q"]
                if self.output_device:
                    player_args.extend(["-a", self.output_device])
                player_args.append(str(media_path))
                subprocess.run(player_args, check=True, timeout=120)
