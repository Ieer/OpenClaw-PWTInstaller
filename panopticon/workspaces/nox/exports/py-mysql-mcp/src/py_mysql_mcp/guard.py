"""只读模式守卫与标识符白名单校验。

对应 TS 版 ``src/guard.ts``。两件事：
1. 只读模式下限制可执行的语句类型；
2. 表名/库名等标识符做白名单校验（原文「防注入」实践的落地）。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .config import AppConfig

# 只读模式允许的语句首关键词
READ_ONLY_PREFIXES = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")

_LINE_COMMENT_RE = re.compile(r"^\s*(?:--[^\n]*\n|#[^\n]*\n|\s+)+")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_FIRST_WORD_RE = re.compile(r"^([A-Za-z]+)")

# 标识符：字母/数字/下划线，可选的 schema.table 形式
_IDENTIFIER_PART_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class GuardError(RuntimeError):
    """只读模式或标识符校验失败时抛出。"""


def get_sql_first_keyword(sql: str) -> str:
    """提取 SQL 首个关键字（忽略前导注释/空白，大小写不敏感）。"""
    stripped = _BLOCK_COMMENT_RE.sub(" ", sql)
    stripped = _LINE_COMMENT_RE.sub("", stripped)
    match = _FIRST_WORD_RE.match(stripped.strip())
    return match.group(1).upper() if match else ""


def is_read_only_sql(sql: str) -> bool:
    """判断是否为只读语句（SELECT / SHOW / DESCRIBE / DESC / EXPLAIN）。"""
    return get_sql_first_keyword(sql) in READ_ONLY_PREFIXES


def assert_readable_in_read_only(sql: str, config: "AppConfig") -> None:
    """mysql_query 使用：只读模式下仅允许只读语句。"""
    if config.read_only and not is_read_only_sql(sql):
        raise GuardError(
            "[guard] Read-only mode is enabled (MYSQL_READ_ONLY=true). "
            "mysql_query only allows SELECT/SHOW/DESCRIBE/EXPLAIN. "
            f'Detected statement starts with: "{get_sql_first_keyword(sql)}". '
            "To perform write operations, disable read-only mode and use mysql_execute."
        )


def assert_execute_allowed(sql: str, config: "AppConfig") -> None:
    """mysql_execute 使用：只读模式下完全禁用。"""
    if config.read_only:
        raise GuardError(
            "[guard] Read-only mode is enabled (MYSQL_READ_ONLY=true). mysql_execute is completely disabled. "
            "To execute DDL/DML statements, set MYSQL_READ_ONLY=false."
        )


def sanitize_identifier(name: str) -> str:
    """校验表名/库名标识符，仅允许字母/数字/下划线及可选的 schema.table 形式。"""
    trimmed = name.strip()
    if not trimmed:
        raise GuardError("[guard] Empty identifier is not allowed.")
    for part in trimmed.split("."):
        if not _IDENTIFIER_PART_RE.match(part):
            raise GuardError(
                f'[guard] Invalid identifier: "{name}". '
                "Only letters, digits and underscores are allowed (optionally schema.table)."
            )
    return trimmed
