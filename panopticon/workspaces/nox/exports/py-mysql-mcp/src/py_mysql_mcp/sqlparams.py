"""把工具契约里的 ``?`` 占位符转换为底层驱动需要的参数风格。

设计动机（参考原文「参数占位符差异」避坑点）：
- 对外保持 MySQL 风格的 ``?`` 占位符（与 TS 版工具契约一致，也最直观）；
- 对内按 SQLAlchemy 方言的 ``paramstyle`` 自动适配：``qmark`` 原样保留、``format`` /
  ``pyformat`` 转成 ``%s`` 并对字面量 ``%`` 做转义。
- 转换过程跳过字符串 / 标识符 / 注释中的 ``?``，避免误伤数据。
"""

from __future__ import annotations

from typing import List, Tuple

SUPPORTED_PARAMSTYLES = ("qmark", "format", "pyformat")


def _scan(sql: str) -> Tuple[List[str], int]:
    """按 SQL 词法切分，返回 (被 ``?`` 分隔的片段列表, ``?`` 个数)。

    只在「普通状态」下把 ``?`` 视为占位符；字符串、反引号标识符、注释中的 ``?`` 保留原文。
    """
    parts: List[str] = []
    buf: List[str] = []
    count = 0
    i = 0
    n = len(sql)
    state = "N"  # N / ' / " / ` / # / line(-) / block(*)

    while i < n:
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if state == "N":
            if c == "'":
                state = "'"
                buf.append(c)
            elif c == '"':
                state = '"'
                buf.append(c)
            elif c == "`":
                state = "`"
                buf.append(c)
            elif c == "#":
                state = "#"
                buf.append(c)
            elif c == "-" and nxt == "-":
                state = "-"
                buf.append("--")
                i += 2
                continue
            elif c == "/" and nxt == "*":
                state = "*"
                buf.append("/*")
                i += 2
                continue
            elif c == "?":
                parts.append("".join(buf))
                buf = []
                count += 1
            else:
                buf.append(c)
        elif state in ("'", '"', "`"):
            q = state
            if c == "\\" and i + 1 < n:  # 反斜杠转义
                buf.append(c)
                buf.append(nxt)
                i += 2
                continue
            if c == q:
                if nxt == q:  # 连续两个引号 = 转义
                    buf.append(c)
                    buf.append(c)
                    i += 2
                    continue
                state = "N"
            buf.append(c)
        elif state in ("#", "-"):
            buf.append(c)
            if c == "\n":
                state = "N"
        elif state == "*":
            buf.append(c)
            if c == "*" and nxt == "/":
                buf.append("/")
                i += 2
                state = "N"
                continue
        i += 1

    parts.append("".join(buf))
    return parts, count


def convert_placeholders(sql: str, paramstyle: str, has_params: bool) -> str:
    """把 ``?`` 占位符转换为指定 paramstyle 的形式。"""
    if paramstyle not in SUPPORTED_PARAMSTYLES:
        raise ValueError(
            f"[sqlparams] Unsupported DBAPI paramstyle: {paramstyle!r}. "
            f"Supported: {', '.join(SUPPORTED_PARAMSTYLES)}."
        )

    if paramstyle == "qmark":
        return sql

    # format / pyformat：底层（PyMySQL 等）使用 % 风格，字面量 % 需转义为 %%
    if has_params:
        sql = sql.replace("%", "%%")
    parts, _ = _scan(sql)
    return "%s".join(parts)


def count_placeholders(sql: str) -> int:
    """统计普通状态下 ``?`` 占位符个数（用于与 params 数量对齐校验）。"""
    _, count = _scan(sql)
    return count
