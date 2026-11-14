"""工具注册总入口：把 4 个 MySQL 工具挂到 FastMCP 实例上。

对应 TS 版 ``src/tools/index.ts``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .query import register_query_tool
from .execute import register_execute_tool
from .list_tables import register_list_tool
from .describe import register_describe_tool

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy.engine import Engine

    from ..config import AppConfig


def register_all_tools(mcp: "FastMCP", engine: "Engine", config: "AppConfig") -> None:
    """注册全部 MySQL 工具。"""
    register_query_tool(mcp, engine, config)
    register_execute_tool(mcp, engine, config)
    register_list_tool(mcp, engine, config)
    register_describe_tool(mcp, engine, config)
