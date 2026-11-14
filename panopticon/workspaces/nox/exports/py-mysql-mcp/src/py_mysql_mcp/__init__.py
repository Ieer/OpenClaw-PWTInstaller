"""py-mysql-mcp：基于 MCP 的 MySQL 访问服务（Python 版）。"""

from .config import AppConfig, ConfigError, load_config

__all__ = ["AppConfig", "ConfigError", "load_config", "__version__"]

__version__ = "0.1.0"
