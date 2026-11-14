"""服务装配：构建 FastMCP 实例并注册工具。

对应 TS 版 ``src/index.ts``（HTTP 服务 + MCP Server）。
传输层：Streamable HTTP，端点为 ``/mcp``（支持 POST / GET / DELETE）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from .tools import register_all_tools

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.engine import Engine

    from .config import AppConfig

logger = logging.getLogger("py_mysql_mcp")

SERVER_NAME = "mysql-mcp-server"
SERVER_VERSION = "0.1.0"


def build_server(config: "AppConfig", engine: "Engine") -> FastMCP:
    """创建 FastMCP 服务并注册全部 MySQL 工具。"""
    mcp = FastMCP(
        name=SERVER_NAME,
        host=config.http_host,
        port=config.http_port,
        streamable_http_path="/mcp",
        json_response=False,
    )
    register_all_tools(mcp, engine, config)
    logger.info("Read-only mode: %s", "ON" if config.read_only else "OFF")
    return mcp


def run(config: "AppConfig", engine: "Engine") -> None:
    """阻塞式启动 Streamable HTTP 服务。"""
    mcp = build_server(config, engine)
    logger.info(
        "MySQL MCP Server listening on http://%s:%s/mcp (endpoint: POST/GET/DELETE /mcp)",
        config.http_host,
        config.http_port,
    )
    mcp.run(transport="streamable-http")
