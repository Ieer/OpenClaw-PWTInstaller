"""应用配置：全部从环境变量读取，不硬编码任何凭据。

对应 TS 版 ``src/config.ts``。遵循原文「凭据环境变量化 / 配置集中一处」的实践：
- 所有 MySQL 连接信息走环境变量；
- 可选 ``DATABASE_URL`` 覆盖，实现「一次编写、多库适配」的切换能力；
- 缺失必填项时启动即报错退出，避免运行时才发现。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:  # 可选依赖：无 python-dotenv 也能运行
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - 仅当未安装时触发
    pass


class ConfigError(RuntimeError):
    """配置缺失或非法时抛出。"""


@dataclass(frozen=True)
class AppConfig:
    # MySQL 连接配置
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: Optional[str]

    # 连接池配置
    pool_size: int

    # 只读模式开关
    read_only: bool

    # HTTP / MCP 服务配置
    http_host: str
    http_port: int

    # 可选：完整连接串覆盖（如 mysql+pymysql://... / sqlite:///./demo.db）
    database_url: Optional[str] = None


def _required(key: str) -> str:
    val = os.environ.get(key)
    if val is None or val == "":
        raise ConfigError(
            f"[config] Missing required environment variable: {key}. "
            "Please check your .env file (see .env.example)."
        )
    return val


def _optional(key: str) -> Optional[str]:
    val = os.environ.get(key)
    return None if val is None or val == "" else val


def _parse_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"[config] Environment variable {key} must be a valid integer, got: {raw}"
        ) from exc


def _parse_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


_cached: Optional[AppConfig] = None


def load_config(force_reload: bool = False) -> AppConfig:
    """加载并校验配置。首次调用读取环境变量，缺失必填项立即抛错。"""
    global _cached
    if _cached is not None and not force_reload:
        return _cached

    database_url = _optional("DATABASE_URL")

    # 有 DATABASE_URL 时可放宽 MySQL_* 必填（便于本地用 SQLite 跑通）
    if database_url:
        mysql_host = _optional("MYSQL_HOST") or "127.0.0.1"
        mysql_user = _optional("MYSQL_USER") or "root"
        mysql_password = _optional("MYSQL_PASSWORD") or ""
    else:
        mysql_host = _required("MYSQL_HOST")
        mysql_user = _required("MYSQL_USER")
        mysql_password = _required("MYSQL_PASSWORD")

    config = AppConfig(
        mysql_host=mysql_host,
        mysql_port=_parse_int("MYSQL_PORT", 3306),
        mysql_user=mysql_user,
        mysql_password=mysql_password,
        mysql_database=_optional("MYSQL_DATABASE"),
        pool_size=_parse_int("MYSQL_POOL_SIZE", 10),
        read_only=_parse_bool("MYSQL_READ_ONLY", False),
        http_host=_optional("MCP_HTTP_HOST") or "127.0.0.1",
        http_port=_parse_int("MCP_HTTP_PORT", 3000),
        database_url=database_url,
    )

    if not 1 <= config.mysql_port <= 65535:
        raise ConfigError(f"[config] MYSQL_PORT must be between 1 and 65535, got: {config.mysql_port}")
    if not 1 <= config.http_port <= 65535:
        raise ConfigError(f"[config] MCP_HTTP_PORT must be between 1 and 65535, got: {config.http_port}")
    if config.pool_size < 1:
        raise ConfigError(f"[config] MYSQL_POOL_SIZE must be >= 1, got: {config.pool_size}")

    _cached = config
    return config
