import importlib

import pytest

from py_mysql_mcp import config as config_mod
from py_mysql_mcp.config import AppConfig, ConfigError, load_config


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(config_mod, "_cached", None)
    for key in (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
        "MYSQL_POOL_SIZE",
        "MYSQL_READ_ONLY",
        "MCP_HTTP_HOST",
        "MCP_HTTP_PORT",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


def test_loads_required_and_defaults(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "db.local")
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.mysql_host == "db.local"
    assert cfg.mysql_port == 3306
    assert cfg.pool_size == 10
    assert cfg.read_only is False
    assert cfg.http_host == "127.0.0.1"
    assert cfg.http_port == 3000


def test_missing_required_raises():
    with pytest.raises(ConfigError):
        load_config()


def test_invalid_port_raises(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "h")
    monkeypatch.setenv("MYSQL_USER", "u")
    monkeypatch.setenv("MYSQL_PASSWORD", "p")
    monkeypatch.setenv("MYSQL_PORT", "99999")
    with pytest.raises(ConfigError):
        load_config()


def test_read_only_bool(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "h")
    monkeypatch.setenv("MYSQL_USER", "u")
    monkeypatch.setenv("MYSQL_PASSWORD", "p")
    monkeypatch.setenv("MYSQL_READ_ONLY", "TRUE")
    assert load_config().read_only is True


def test_database_url_relaxes_mysql_required(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./demo.db")
    cfg = load_config()
    assert cfg.database_url == "sqlite:///./demo.db"
    assert cfg.mysql_user == "root"


def test_config_is_cached(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "h")
    monkeypatch.setenv("MYSQL_USER", "u")
    monkeypatch.setenv("MYSQL_PASSWORD", "p")
    assert load_config() is load_config()
