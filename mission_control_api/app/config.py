from pydantic import BaseModel


def _is_placeholder_token(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    upper = raw.upper()
    return upper.startswith("CHANGE_ME") or upper in {"TODO", "REPLACE_ME", "YOUR_TOKEN"}


class Settings(BaseModel):
    auth_token: str | None = None

    database_url: str = (
        "postgresql+asyncpg://mission_control:mission_control@mc-postgres:5432/mission_control"
    )
    redis_url: str = "redis://mc-redis:6379/0"
    redis_stream_key: str = "mc:events"
    global_skills_dir: str = "/data/global-skills"
    agent_homes_dir: str = "/data/agent-homes"
    knowledge_raw_sources_dir: str = "/data/knowledge-sources"
    knowledge_embedding_enabled: bool = False
    knowledge_embedding_model: str | None = None
    knowledge_embedding_base_url: str | None = None
    knowledge_embedding_api_key: str | None = None
    knowledge_embedding_api_protocol: str = "openai-embeddings"
    knowledge_embedding_dimensions: int | None = None
    knowledge_embedding_timeout_seconds: float = 20.0
    agent_token_map: dict[str, str] = {}
    agent_manifest_path: str = "/app/panopticon_agents.manifest.yaml"
    agent_slugs: str = ""
    chat_host: str = "127.0.0.1"
    enable_direct_agent_links: bool = False
    chat_upstream_port: int = 26216
    chat_force_loopback_headers: bool = True
    chat_inject_script_enabled: bool = True
    chat_clear_device_auth_storage: bool = True
    chat_inject_gateway_settings: bool = True
    chat_dom_avatar_rewrite: bool = True
    chat_sanitize_connect_auth: bool = True
    chat_strip_stale_device_fields: bool = True
    chat_force_token_in_connect: bool = True
    chat_rewrite_control_ui_config: bool = True
    chat_rewrite_avatar_payloads: bool = True
    agent_controller_url: str = "http://mission-control-agent-controller:9091"
    agent_controller_auth_token: str | None = None
    agent_controller_timeout_seconds: float = 5.0


def _env_flag(name: str, default: bool) -> bool:
    import os

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    import os

    raw_embedding_dimensions = (os.getenv("MC_KNOWLEDGE_EMBEDDING_DIMENSIONS") or "").strip()

    token_map_str = (os.getenv("MC_CHAT_AGENT_TOKEN_MAP") or os.getenv("MISSION_CONTROL_CHAT_AGENT_TOKEN_MAP") or "").strip()
    agent_token_map = {}
    if token_map_str:
        for pair in token_map_str.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                token_value = v.strip()
                if k.strip() and not _is_placeholder_token(token_value):
                    agent_token_map[k.strip()] = token_value

    return Settings(
        auth_token=os.getenv("MC_AUTH_TOKEN") or None,
        database_url=os.getenv("MC_DATABASE_URL")
        or "postgresql+asyncpg://mission_control:mission_control@mc-postgres:5432/mission_control",
        redis_url=os.getenv("MC_REDIS_URL") or "redis://mc-redis:6379/0",
        redis_stream_key=os.getenv("MC_REDIS_STREAM_KEY") or "mc:events",
        global_skills_dir=os.getenv("MC_GLOBAL_SKILLS_DIR") or "/data/global-skills",
        agent_homes_dir=os.getenv("MC_AGENT_HOMES_DIR") or "/data/agent-homes",
        knowledge_raw_sources_dir=os.getenv("MC_KNOWLEDGE_RAW_SOURCES_DIR") or "/data/knowledge-sources",
        knowledge_embedding_enabled=_env_flag("MC_KNOWLEDGE_EMBEDDING_ENABLED", False),
        knowledge_embedding_model=(os.getenv("MC_KNOWLEDGE_EMBEDDING_MODEL") or "").strip() or None,
        knowledge_embedding_base_url=(os.getenv("MC_KNOWLEDGE_EMBEDDING_BASE_URL") or "").strip() or None,
        knowledge_embedding_api_key=(os.getenv("MC_KNOWLEDGE_EMBEDDING_API_KEY") or "").strip() or None,
        knowledge_embedding_api_protocol=(os.getenv("MC_KNOWLEDGE_EMBEDDING_API_PROTOCOL") or "openai-embeddings").strip() or "openai-embeddings",
        knowledge_embedding_dimensions=int(raw_embedding_dimensions) if raw_embedding_dimensions else None,
        knowledge_embedding_timeout_seconds=float((os.getenv("MC_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS") or "20.0").strip()),
        agent_token_map=agent_token_map,
        agent_manifest_path=(os.getenv("MISSION_CONTROL_AGENT_MANIFEST_PATH") or "/app/panopticon_agents.manifest.yaml").strip() or "/app/panopticon_agents.manifest.yaml",
        agent_slugs=(os.getenv("MISSION_CONTROL_AGENT_SLUGS") or "").strip(),
        chat_host=(os.getenv("MC_CHAT_HOST") or os.getenv("MISSION_CONTROL_CHAT_HOST") or "127.0.0.1").strip() or "127.0.0.1",
        enable_direct_agent_links=(
            _env_flag("MC_CHAT_ENABLE_DIRECT_AGENT_LINKS", False)
            if os.getenv("MC_CHAT_ENABLE_DIRECT_AGENT_LINKS") is not None
            else _env_flag("MISSION_CONTROL_ENABLE_DIRECT_AGENT_LINKS", False)
        ),
        chat_upstream_port=int((os.getenv("MC_CHAT_UPSTREAM_PORT") or "26216").strip()),
        chat_force_loopback_headers=_env_flag("MC_CHAT_PROXY_FORCE_LOOPBACK_HEADERS", True),
        chat_inject_script_enabled=_env_flag("MC_CHAT_COMPAT_INJECT_SCRIPT_ENABLED", True),
        chat_clear_device_auth_storage=_env_flag("MC_CHAT_COMPAT_CLEAR_DEVICE_AUTH_STORAGE", True),
        chat_inject_gateway_settings=_env_flag("MC_CHAT_COMPAT_INJECT_GATEWAY_SETTINGS", True),
        chat_dom_avatar_rewrite=_env_flag("MC_CHAT_COMPAT_DOM_AVATAR_REWRITE", True),
        chat_sanitize_connect_auth=_env_flag("MC_CHAT_COMPAT_SANITIZE_CONNECT_AUTH", True),
        chat_strip_stale_device_fields=_env_flag("MC_CHAT_COMPAT_STRIP_STALE_DEVICE_FIELDS", True),
        chat_force_token_in_connect=_env_flag("MC_CHAT_COMPAT_FORCE_TOKEN_IN_CONNECT", True),
        chat_rewrite_control_ui_config=_env_flag("MC_CHAT_COMPAT_REWRITE_CONTROL_UI_CONFIG", True),
        chat_rewrite_avatar_payloads=_env_flag("MC_CHAT_COMPAT_REWRITE_AVATAR_PAYLOADS", True),
        agent_controller_url=(os.getenv("MC_AGENT_CONTROLLER_URL") or "http://mission-control-agent-controller:9091").strip(),
        agent_controller_auth_token=(os.getenv("MC_AGENT_CONTROLLER_AUTH_TOKEN") or "").strip() or None,
        agent_controller_timeout_seconds=float((os.getenv("MC_AGENT_CONTROLLER_TIMEOUT_SECONDS") or "5.0").strip()),
    )
