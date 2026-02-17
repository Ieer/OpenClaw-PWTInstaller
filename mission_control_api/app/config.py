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


def load_settings() -> Settings:
    import os

    return Settings(
        auth_token=os.getenv("MC_AUTH_TOKEN") or None,
        database_url=os.getenv("MC_DATABASE_URL")
        or "postgresql+asyncpg://mission_control:mission_control@mc-postgres:5432/mission_control",
        redis_url=os.getenv("MC_REDIS_URL") or "redis://mc-redis:6379/0",
        redis_stream_key=os.getenv("MC_REDIS_STREAM_KEY") or "mc:events",
        global_skills_dir=os.getenv("MC_GLOBAL_SKILLS_DIR") or "/data/global-skills",
        agent_homes_dir=os.getenv("MC_AGENT_HOMES_DIR") or "/data/agent-homes",
    )
