from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - handled at runtime on minimal systems
    yaml = None


@dataclass(slots=True)
class TopicConfig:
    wake: str = "wakeup"
    asr: str = "asr"
    text_response: str = "text_response"
    tts: str = "tts_topic"
    tts_request: str = "tts_request"


@dataclass(slots=True)
class AudioConfig:
    mic_device: str = ""
    output_device: str = ""
    sample_rate: int = 16000
    channels: int = 1
    max_utterance_seconds: float = 5.0
    silence_timeout_ms: int = 900
    energy_threshold: float = 1200.0


@dataclass(slots=True)
class AsrConfig:
    engine: str = "dummy"
    language: str = "zh-CN"
    dummy_text: str = "指挥 帮我建个任务给 health：检查今晚备份状态"
    model_path: str = ""
    http_url_env: str = "OPENCLAW_ASR_HTTP_URL"
    http_token_env: str = "OPENCLAW_ASR_HTTP_TOKEN"


@dataclass(slots=True)
class TtsConfig:
    engine: str = "espeak"
    voice: str = "zh"
    speed: int = 165
    model_path: str = ""
    command: str = ""


@dataclass(slots=True)
class MissionControlConfig:
    api_url: str = "http://127.0.0.1:18910"
    auth_token_env: str = "MC_AUTH_TOKEN"
    feed_limit: int = 80
    poll_interval_seconds: float = 1.0


@dataclass(slots=True)
class AppConfig:
    topics: TopicConfig = field(default_factory=TopicConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)
    mission_control: MissionControlConfig = field(default_factory=MissionControlConfig)


def env_text(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip() or default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def load_yaml_config(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML config files")
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def app_config_from_dict(data: dict[str, Any] | None = None) -> AppConfig:
    data = data or {}
    topics = _section(data, "topics")
    audio = _section(data, "audio")
    asr = _section(data, "asr")
    tts = _section(data, "tts")
    mission_control = _section(data, "mission_control")

    return AppConfig(
        topics=TopicConfig(
            wake=str(topics.get("wake", "wakeup") or "wakeup"),
            asr=str(topics.get("asr", "asr") or "asr"),
            text_response=str(topics.get("text_response", "text_response") or "text_response"),
            tts=str(topics.get("tts", "tts_topic") or "tts_topic"),
            tts_request=str(topics.get("tts_request", "tts_request") or "tts_request"),
        ),
        audio=AudioConfig(
            mic_device=str(audio.get("mic_device", "") or ""),
            output_device=str(audio.get("output_device", "") or ""),
            sample_rate=_as_int(audio.get("sample_rate"), 16000),
            channels=_as_int(audio.get("channels"), 1),
            max_utterance_seconds=_as_float(audio.get("max_utterance_seconds"), 5.0),
            silence_timeout_ms=_as_int(audio.get("silence_timeout_ms"), 900),
            energy_threshold=_as_float(audio.get("energy_threshold"), 1200.0),
        ),
        asr=AsrConfig(
            engine=str(asr.get("engine", "dummy") or "dummy"),
            language=str(asr.get("language", "zh-CN") or "zh-CN"),
            dummy_text=str(
                asr.get("dummy_text", "指挥 帮我建个任务给 health：检查今晚备份状态")
                or "指挥 帮我建个任务给 health：检查今晚备份状态"
            ),
            model_path=str(asr.get("model_path", "") or ""),
            http_url_env=str(asr.get("http_url_env", "OPENCLAW_ASR_HTTP_URL") or "OPENCLAW_ASR_HTTP_URL"),
            http_token_env=str(asr.get("http_token_env", "OPENCLAW_ASR_HTTP_TOKEN") or "OPENCLAW_ASR_HTTP_TOKEN"),
        ),
        tts=TtsConfig(
            engine=str(tts.get("engine", "espeak") or "espeak"),
            voice=str(tts.get("voice", "zh") or "zh"),
            speed=_as_int(tts.get("speed"), 165),
            model_path=str(tts.get("model_path", "") or ""),
            command=str(tts.get("command", "") or ""),
        ),
        mission_control=MissionControlConfig(
            api_url=env_text("MC_API_URL", str(mission_control.get("api_url", "http://127.0.0.1:18910") or "http://127.0.0.1:18910")),
            auth_token_env=str(mission_control.get("auth_token_env", "MC_AUTH_TOKEN") or "MC_AUTH_TOKEN"),
            feed_limit=_as_int(mission_control.get("feed_limit"), 80),
            poll_interval_seconds=_as_float(mission_control.get("poll_interval_seconds"), 1.0),
        ),
    )


def load_app_config(path: str | Path | None = None) -> AppConfig:
    return app_config_from_dict(load_yaml_config(path))
