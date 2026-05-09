from __future__ import annotations

import json
import urllib.error
import urllib.request

from .asr_base import AsrEngine


class HttpAsrEngine(AsrEngine):
    """Simple HTTP ASR adapter.

    It POSTs WAV bytes as `application/octet-stream` and expects JSON with one
    of these fields: `text`, `transcript`, or `result.text`.
    """

    def __init__(self, *, url: str, token: str = "", language: str = "zh-CN") -> None:
        self.url = url.strip()
        self.token = token.strip()
        self.language = language

    def transcribe(self, wav_bytes: bytes, *, sample_rate: int, language: str) -> str:
        if not self.url:
            raise RuntimeError("HTTP ASR URL is empty")
        headers = {
            "Content-Type": "application/octet-stream",
            "Accept": "application/json",
            "X-Audio-Sample-Rate": str(sample_rate),
            "X-ASR-Language": language or self.language,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=wav_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"HTTP ASR request failed: {exc}") from exc
        payload = json.loads(raw)
        if isinstance(payload, dict):
            if payload.get("text"):
                return str(payload["text"]).strip()
            if payload.get("transcript"):
                return str(payload["transcript"]).strip()
            result = payload.get("result")
            if isinstance(result, dict) and result.get("text"):
                return str(result["text"]).strip()
        return ""
