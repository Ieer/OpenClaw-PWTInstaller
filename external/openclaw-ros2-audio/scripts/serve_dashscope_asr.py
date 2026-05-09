#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _load_scalar_config(path: str, key: str) -> str:
    if not path:
        return ""
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return ""
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        current_key, raw_value = line.split(":", 1)
        if current_key.strip() != key:
            continue
        value = raw_value.split("#", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value.strip()
    return ""


def _extract_text(result: Any) -> str:
    try:
        sentences = result.get_sentence()
    except Exception:
        sentences = None
    if sentences and isinstance(sentences, list):
        return str(sentences[0].get("text") or "").strip()

    output = getattr(result, "output", None)
    if isinstance(output, dict):
        for key in ("text", "transcript"):
            if output.get(key):
                return str(output[key]).strip()
        sentence_list = output.get("sentence") or output.get("sentences")
        if isinstance(sentence_list, list) and sentence_list:
            first = sentence_list[0]
            if isinstance(first, dict) and first.get("text"):
                return str(first["text"]).strip()
    return ""


class DashScopeAsrServer(ThreadingHTTPServer):
    api_key: str
    model: str
    sample_rate: int
    tmp_dir: str


class DashScopeAsrHandler(BaseHTTPRequestHandler):
    server: DashScopeAsrServer
    server_version = "openclaw-dashscope-asr/0.1"

    def do_GET(self) -> None:
        if self.path.rstrip("/") != "/health":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_json({"ok": True, "model": self.server.model, "sample_rate": self.server.sample_rate})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/asr":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length") or "0")
        if content_length <= 0:
            self._send_json({"error": "empty audio payload"}, status=HTTPStatus.BAD_REQUEST)
            return

        wav_bytes = self.rfile.read(content_length)
        try:
            text = self._recognize(wav_bytes)
        except Exception as exc:
            self._send_json({"error": "asr_failed", "message": str(exc)[:240]}, status=HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"text": text, "transcript": text, "result": {"text": text}})

    def _recognize(self, wav_bytes: bytes) -> str:
        import dashscope  # type: ignore
        from dashscope.audio.asr import Recognition  # type: ignore

        dashscope.api_key = self.server.api_key
        with tempfile.NamedTemporaryFile(dir=self.server.tmp_dir, suffix=".wav", delete=False) as fp:
            fp.write(wav_bytes)
            wav_path = fp.name
        try:
            recognition = Recognition(
                model=self.server.model,
                format="wav",
                sample_rate=self.server.sample_rate,
                callback=None,
            )
            result = recognition.call(wav_path)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

        status_code = int(getattr(result, "status_code", 0) or 0)
        if status_code != HTTPStatus.OK:
            message = getattr(result, "message", "") or getattr(result, "error_message", "") or "DashScope ASR returned non-OK status"
            raise RuntimeError(f"DashScope HTTP {status_code}: {message}")
        return _extract_text(result)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashscope-asr] {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw-compatible HTTP ASR wrapper for DashScope Paraformer.")
    parser.add_argument("--host", default=os.getenv("OPENCLAW_TONGYI_ASR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("OPENCLAW_TONGYI_ASR_PORT", "18081")))
    parser.add_argument("--config", default=os.getenv("OPENCLAW_TONGYI_CONFIG", ""))
    parser.add_argument("--model", default=os.getenv("OPENCLAW_TONGYI_ASR_MODEL", ""))
    parser.add_argument("--sample-rate", type=int, default=int(os.getenv("OPENCLAW_TONGYI_ASR_SAMPLE_RATE", "0") or "0"))
    parser.add_argument("--tmp-dir", default=os.getenv("OPENCLAW_TONGYI_ASR_TMPDIR", "/tmp"))
    args = parser.parse_args()

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip() or _load_scalar_config(args.config, "tongyi_api_key")
    model = args.model.strip() or _load_scalar_config(args.config, "oline_asr_model") or "paraformer-realtime-8k-v2"
    sample_rate = int(args.sample_rate or 0) or int(_load_scalar_config(args.config, "oline_asr_sample_rate") or "16000")
    if not api_key:
        raise SystemExit("DASHSCOPE_API_KEY is required or provide --config with tongyi_api_key")

    Path(args.tmp_dir).mkdir(parents=True, exist_ok=True)
    server = DashScopeAsrServer((args.host, args.port), DashScopeAsrHandler)
    server.api_key = api_key
    server.model = model
    server.sample_rate = sample_rate
    server.tmp_dir = args.tmp_dir
    print(f"[dashscope-asr] listening on http://{args.host}:{args.port}/asr model={model} sample_rate={sample_rate}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())