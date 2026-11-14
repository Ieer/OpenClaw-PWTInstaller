"""工具的公共辅助：统一的成功/失败返回格式。

对应 TS 版 ``src/tools/query.ts`` 里的 ``formatError`` / ``makeToolError``。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from mcp.server.fastmcp.exceptions import ToolError

logger = logging.getLogger("py_mysql_mcp")


def ok(payload: dict) -> str:
    """把结果序列化为 JSON 文本返回给模型。"""
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def tool_error(exc: BaseException, tool: str, sql: Optional[str] = None) -> ToolError:
    """构造结构化错误返回，不暴露凭据，保留可用于排查的错误码/消息。"""
    errno = getattr(exc, "errno", None)
    code = getattr(exc, "code", None)
    message = getattr(exc, "sqlMessage", None) or str(exc) or exc.__class__.__name__
    logger.error("[%s] error: %s | sql=%s", tool, message, sql)
    body = {
        "success": False,
        "error": {
            "message": message,
            "errno": errno,
            "code": code,
        },
    }
    return ToolError(ok(body))
