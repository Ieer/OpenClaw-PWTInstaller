from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request
from urllib.parse import urlsplit

MAX_BYTES = 3 * 1024 * 1024
MAX_SECONDS = 30
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
AGENTS = {"personal", "nox", "metrics", "growth", "email", "writing", "health", "trades"}
SERVICE_HOST = "agent-speech"
ASR_URL = f"http://{SERVICE_HOST}:18081/asr"
TTS_BASE_URL = f"http://{SERVICE_HOST}:18081/v1"
LEGACY_ASR_URL = "http://personal-speech:18081/asr"


def speech_principals(credentials: dict) -> dict[str, str]:
    if credentials.get("tokens", {}).get("personal", credentials.get("token")) != credentials.get("token"):
        raise ValueError("personal legacy token cannot be replaced implicitly")
    principals = {"personal": credentials.get("token", ""), **credentials.get("tokens", {})}
    if any(agent not in AGENTS or not isinstance(token, str) or len(token) < 32 for agent, token in principals.items()):
        raise ValueError("invalid speech principal")
    if len(set(principals.values())) != len(principals):
        raise ValueError("speech tokens must be role-specific")
    return principals


def authenticate_speech(authorization: str, principals: dict[str, str]) -> str | None:
    for agent, token in principals.items():
        if hmac.compare_digest(authorization, "Bearer " + token):
            return agent
    return None


def speech_input(value: dict) -> str:
    if not isinstance(value, dict) or value.get("model") != "local-edge":
        raise ValueError("unsupported speech model")
    if value.get("voice", TTS_VOICE) != TTS_VOICE or value.get("response_format", "mp3") != "mp3":
        raise ValueError("unsupported speech output")
    text = value.get("input")
    if not isinstance(text, str) or not text.strip() or len(text) > 1000:
        raise ValueError("speech text exceeds budget")
    return text


def synthesize(text: str) -> bytes:
    import edge_tts

    async def collect():
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice=TTS_VOICE).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
                if len(audio) > MAX_BYTES:
                    raise ValueError("speech output exceeds budget")
        if not audio:
            raise ValueError("empty speech output")
        return bytes(audio)

    return asyncio.run(asyncio.wait_for(collect(), timeout=30))


def prepare_credentials(source: Path, destination: Path, client_path: Path) -> None:
    import yaml
    settings = yaml.safe_load(source.read_text())
    model = str(settings.get("oline_asr_model") or "paraformer-realtime-8k-v2").strip()
    if model not in {"paraformer-realtime-8k-v2", "paraformer-realtime-v2"}:
        raise ValueError("unsupported speech model")
    key = str(settings.get("tongyi_api_key") or "").strip()
    if not key:
        raise ValueError("speech key missing")
    previous = json.loads(destination.read_text()) if destination.exists() else {}
    token = previous.get("token") or secrets.token_urlsafe(32)
    for path, value in ((destination, {**previous, "api_key": key, "model": model, "token": token}),
                        (client_path, {"url": ASR_URL, "token": token})):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name(path.name + ".part")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump(value, output)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def write_private_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".part")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def agent_speech_batch(config: dict, token: str, proxy_ip: str) -> list[dict]:
    media = config.get("tools", {}).get("media", {})
    if media.get("models") or config.get("tts") or config.get("talk", {}).get("provider"):
        raise ValueError("custom speech configuration requires manual review")
    if config.get("talk", {}).get("realtime", {}).get("mode") not in (None, "stt-tts"):
        raise ValueError("custom Talk mode requires manual review")
    batch = [
        {"path": "tools.media.models", "value": [{"type": "cli", "command": "/usr/bin/python3",
            "args": ["/home/node/.openclaw/voice/agent_speech.py", "transcribe", "{{AttachmentPath}}",
                     "--credentials", "/home/node/.openclaw/voice/speech-client.json"],
            "capabilities": ["audio"], "timeoutSeconds": 80}]},
        {"path": "tools.media.audio.enabled", "value": True},
        {"path": "tts", "value": {"auto": "off", "provider": "openai", "maxTextLength": 1000,
            "timeoutMs": 30000, "modelOverrides": {"enabled": False}, "providers": {"openai": {
                "apiKey": token, "baseUrl": TTS_BASE_URL,
                "model": "local-edge", "speakerVoice": TTS_VOICE}}}},
        {"path": "talk.realtime.mode", "value": "stt-tts"},
    ]
    trusted = config.get("gateway", {}).get("trustedProxies", [])
    if trusted == ["172.21.0.15"] and proxy_ip != "172.21.0.15":
        batch.append({"path": "gateway.trustedProxies", "value": [proxy_ip]})
    elif proxy_ip not in trusted:
        raise ValueError("custom proxy trust requires manual review")
    return batch


def prepare_agents(service_path: Path, homes: Path, agents: list[str], proxy_ip: str, stamp: str) -> list[dict]:
    from ipaddress import ip_address

    if not agents or any(agent not in AGENTS or agent == "personal" for agent in agents):
        raise ValueError("only explicitly selected additional speech roles are supported")
    if not ip_address(proxy_ip).is_private or not stamp.isdigit():
        raise ValueError("invalid preparation metadata")
    service = json.loads(service_path.read_text())
    principals = speech_principals(service)
    prepared = []
    for agent in agents:
        home = homes / agent
        raw = (home / "openclaw.json").read_bytes()
        config = json.loads(raw)
        token = principals.get(agent) or secrets.token_urlsafe(32)
        batch = agent_speech_batch(config, token, proxy_ip)
        client = home / "voice" / "speech-client.json"
        if client.exists():
            existing = json.loads(client.read_text())
            if existing.get("token") != token or existing.get("url") not in {ASR_URL, LEGACY_ASR_URL}:
                raise ValueError("existing custom speech client requires manual review")
        principals[agent] = token
        prepared.append({"agent": agent, "raw": raw, "batch": batch, "client": client})
    service["tokens"] = {agent: token for agent, token in principals.items() if agent != "personal"}
    speech_principals(service)
    report = []
    for item in prepared:
        directory = homes / item["agent"] / "voice"
        backup = directory / f"openclaw-before-speech-{stamp}.json"
        if backup.exists():
            raise ValueError("preparation backup already exists")
        write_private_json(backup, json.loads(item["raw"]))
        write_private_json(directory / f"speech-batch-{stamp}.json", item["batch"])
        write_private_json(item["client"], {"url": ASR_URL,
                                               "token": principals[item["agent"]], "agent_slug": item["agent"]})
        report.append({"agent": item["agent"], "config_sha256": hashlib.sha256(item["raw"]).hexdigest()})
    write_private_json(service_path, service)
    return report


def prepare_tts_config(client_path: Path, destination: Path) -> None:
    credentials = json.loads(client_path.read_text())
    endpoint = credentials.get("url")
    token = credentials.get("token")
    if endpoint not in {ASR_URL, LEGACY_ASR_URL} or not isinstance(token, str) or len(token) < 32:
        raise ValueError("invalid agent speech client configuration")
    operations = [
        {"path": "tts.provider", "value": "openai"},
        {"path": "tts.providers.openai", "value": {"apiKey": token,
            "baseUrl": TTS_BASE_URL, "model": "local-edge", "speakerVoice": TTS_VOICE}},
        {"path": "tts.providers.microsoft.enabled", "value": False},
    ]
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(operations, output)


def transcribe_file(path: Path, credentials: dict) -> str:
    endpoint = urlsplit(credentials["url"])
    if endpoint.scheme != "http" or endpoint.hostname not in {SERVICE_HOST, "personal-speech", "127.0.0.1", "localhost"}:
        raise ValueError("invalid speech service endpoint")
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("invalid speech service endpoint")
    with path.open("rb") as source:
        audio = source.read(MAX_BYTES + 1)
    if not audio or len(audio) > MAX_BYTES:
        raise ValueError("audio exceeds the input budget")
    upload = request.Request(credentials["url"], data=audio, headers={
        "Content-Type": "application/octet-stream", "Authorization": "Bearer " + credentials["token"]})
    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    with opener.open(upload, timeout=75) as response:
        value = json.loads(response.read(65536))
    text = value.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("invalid transcription response")
    return text.strip()


def recognize(audio: bytes, credentials: dict) -> str:
    import dashscope
    from dashscope.audio.asr import Recognition

    model = credentials["model"]
    if model not in {"paraformer-realtime-8k-v2", "paraformer-realtime-v2"}:
        raise ValueError("unsupported speech model")
    rate = 8000 if "-8k-" in model else 16000
    with tempfile.TemporaryDirectory(prefix="agent-speech-") as directory:
        source = Path(directory) / "input.audio"
        output = Path(directory) / "input.wav"
        source.write_bytes(audio)
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-protocol_whitelist", "file,pipe", "-i", str(source), "-t", str(MAX_SECONDS + 1), "-ar", str(rate), "-ac", "1",
                        "-c:a", "pcm_s16le", str(output)], check=True, timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with wave.open(str(output), "rb") as normalized:
            duration = normalized.getnframes() / normalized.getframerate()
        if not 0 < duration <= MAX_SECONDS:
            raise ValueError("audio exceeds the duration budget")
        dashscope.api_key = credentials["api_key"]
        result = Recognition(model=model, format="wav", sample_rate=rate, callback=None).call(str(output))
        if int(getattr(result, "status_code", 0) or 0) != 200:
            raise RuntimeError("speech provider failed")
        sentences = result.get_sentence()
        if isinstance(sentences, dict):
            sentences = [sentences]
        text = "".join(str(item.get("text") or "") for item in (sentences or []) if isinstance(item, dict))
        if not text.strip() or len(text) > 4000:
            raise ValueError("no usable speech transcript")
        return text.strip()


def create_server(credentials: dict, *, host="0.0.0.0", port=18081, recognizer=recognize, synthesizer=synthesize):
    if len(credentials.get("token", "")) < 32 or not credentials.get("api_key"):
        raise ValueError("private speech credentials are required")
    principals = speech_principals(credentials)
    admission = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_args):
            pass

        def respond(self, status: int, value: dict):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.respond(200 if self.path == "/health" else 404, {"ok": self.path == "/health"})

        def do_POST(self):
            if authenticate_speech(self.headers.get("Authorization", ""), principals) is None:
                return self.respond(403, {"error": "speech authentication required"})
            if self.path not in {"/asr", "/v1/audio/speech"}:
                return self.respond(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            limit = 8192 if self.path == "/v1/audio/speech" else MAX_BYTES
            if not 0 < length <= limit:
                return self.respond(413, {"error": "audio input budget exceeded"})
            if not admission.acquire(blocking=False):
                return self.respond(429, {"error": "speech service busy"})
            try:
                audio = self.rfile.read(length)
                if len(audio) != length:
                    raise ValueError("incomplete audio")
                if self.path == "/v1/audio/speech":
                    try:
                        text = speech_input(json.loads(audio))
                    except (ValueError, TypeError):
                        return self.respond(400, {"error": "invalid speech request"})
                    output = synthesizer(text)
                    if not isinstance(output, bytes) or not 0 < len(output) <= MAX_BYTES:
                        raise ValueError("invalid speech audio")
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Content-Length", str(len(output)))
                    self.end_headers()
                    self.wfile.write(output)
                    return
                text = recognizer(audio, credentials)
                self.respond(200, {"text": text})
            except Exception:
                self.respond(502, {"error": "speech transcription failed"})
            finally:
                admission.release()

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("serve", "transcribe", "prepare", "prepare-tts-config", "prepare-agents"))
    parser.add_argument("audio", nargs="?", type=Path)
    parser.add_argument("--credentials", type=Path, default=Path("/run/agent-speech.json"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--agent-homes", type=Path, default=Path("panopticon/agent-homes"))
    parser.add_argument("--agents")
    parser.add_argument("--proxy-ip")
    parser.add_argument("--stamp")
    args = parser.parse_args()
    try:
        if args.action == "prepare-agents":
            if not args.agents or not args.proxy_ip or not args.stamp:
                raise ValueError("explicit agents, actual proxy IP and timestamp required")
            report = prepare_agents(args.credentials, args.agent_homes, args.agents.split(","), args.proxy_ip, args.stamp)
            print(json.dumps(report))
            return 0
        if args.action == "prepare-tts-config":
            if args.client is None:
                raise ValueError("client source required")
            prepare_tts_config(args.client, args.credentials)
            print("private TTS config batch prepared; credentials are not printed")
            return 0
        if args.action == "prepare":
            if args.source is None or args.client is None:
                raise ValueError("source and client destination required")
            prepare_credentials(args.source, args.credentials, args.client)
            print("private agent speech credentials prepared; secrets are not printed")
            return 0
        credentials = json.loads(args.credentials.read_text())
        if args.action == "transcribe":
            if args.audio is None:
                raise ValueError("audio input required")
            print(transcribe_file(args.audio, credentials))
        else:
            create_server(credentials).serve_forever()
    except Exception:
        print("agent speech operation failed; verify private configuration", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())