from pydantic import BaseModel


class Settings(BaseModel):
    auth_token: str | None = None

    database_url: str = (
        "postgresql+asyncpg://mission_control:mission_control@mc-postgres:5432/mission_control"
    )
    redis_url: str = "redis://mc-redis:6379/0"
    redis_stream_key: str = "mc:events"
    global_skills_dir: str = "/data/global-skills"
    agent_homes_dir: str = "/data/agent-homes"
    agent_token_map: dict[str, str] = {}
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


def _env_flag(name: str, default: bool) -> bool:
    import os

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    import os
    
    token_map_str = os.getenv("MISSION_CONTROL_CHAT_AGENT_TOKEN_MAP", "")
    agent_token_map = {}
    if token_map_str:
        for pair in token_map_str.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                agent_token_map[k.strip()] = v.strip()

    return Settings(
        auth_token=os.getenv("MC_AUTH_TOKEN") or None,
        database_url=os.getenv("MC_DATABASE_URL")
        or "postgresql+asyncpg://mission_control:mission_control@mc-postgres:5432/mission_control",
        redis_url=os.getenv("MC_REDIS_URL") or "redis://mc-redis:6379/0",
        redis_stream_key=os.getenv("MC_REDIS_STREAM_KEY") or "mc:events",
        global_skills_dir=os.getenv("MC_GLOBAL_SKILLS_DIR") or "/data/global-skills",
        agent_homes_dir=os.getenv("MC_AGENT_HOMES_DIR") or "/data/agent-homes",
        agent_token_map=agent_token_map,
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
    )
