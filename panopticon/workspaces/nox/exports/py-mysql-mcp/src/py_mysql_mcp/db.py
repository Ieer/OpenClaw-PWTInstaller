"""数据库访问层：SQLAlchemy Engine（连接池 + 方言）+ 参数化执行。

对应 TS 版 ``src/db.ts``。参考原文结论，这里用 SQLAlchemy 承载「连接池 + 方言适配」，
把「换库只改一处」落在 ``build_url`` 上；执行任意 SQL 时坚持参数绑定，杜绝拼串注入。
"""

from __future__ import annotations

import datetime as _dt
import decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import AppConfig
from .guard import sanitize_identifier
from .sqlparams import convert_placeholders, count_placeholders


class ParamCountError(ValueError):
    """``?`` 占位符数量与参数个数不一致。"""


def build_url(config: AppConfig) -> str:
    """构造 SQLAlchemy 连接串。集中一处，迁移数据库时只改这里。"""
    if config.database_url:
        return config.database_url
    pwd = quote_plus(config.mysql_password)
    db = f"/{config.mysql_database}" if config.mysql_database else ""
    return (
        f"mysql+pymysql://{config.mysql_user}:{pwd}"
        f"@{config.mysql_host}:{config.mysql_port}{db}?charset=utf8mb4"
    )


def create_pool(config: AppConfig) -> Engine:
    """创建带连接池的 SQLAlchemy Engine。"""
    url = build_url(config)
    kwargs: Dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        # SQLite 用于本地演示；不设连接池大小限制
        if ":memory:" not in url:
            kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = config.pool_size
        kwargs["max_overflow"] = 0
        kwargs["pool_recycle"] = 3600
    return create_engine(url, **kwargs)


def close_pool(engine: Engine) -> None:
    """释放连接池。"""
    engine.dispose()


def _prepare(engine: Engine, sql: str, params: Sequence[Any]) -> str:
    n_marks = count_placeholders(sql)
    if n_marks != len(params):
        raise ParamCountError(
            f"[db] Parameter count mismatch: SQL has {n_marks} '?' placeholder(s) "
            f"but {len(params)} parameter(s) were provided."
        )
    return convert_placeholders(sql, engine.dialect.paramstyle, has_params=bool(params))


def _use_database(conn, database: Optional[str], engine: Engine) -> None:
    """按需切换当前数据库（MySQL 专有；其它方言跳过）。"""
    if database and engine.dialect.name == "mysql":
        safe = sanitize_identifier(database)
        conn.exec_driver_sql(f"USE `{safe}`")


def _jsonable(value: Any) -> Any:
    """把驱动返回的非 JSON 原生类型转成可序列化形式。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value) if value == value.to_integral_value() else str(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return str(value)


def query_rows(
    engine: Engine,
    sql: str,
    params: Optional[Iterable[Any]] = None,
    database: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """执行返回结果集的语句（主要用于 SELECT），返回行字典列表。"""
    params = list(params or [])
    stmt = _prepare(engine, sql, params)
    with engine.connect() as conn:
        _use_database(conn, database, engine)
        if params:
            result = conn.exec_driver_sql(stmt, tuple(params))
        else:
            result = conn.exec_driver_sql(stmt)
        rows = result.mappings().all()
        return [{k: _jsonable(v) for k, v in row.items()} for row in rows]


def execute_statement(
    engine: Engine,
    sql: str,
    params: Optional[Iterable[Any]] = None,
    database: Optional[str] = None,
) -> Dict[str, Any]:
    """执行不返回结果集的语句（DDL/DML），返回 affectedRows / insertId 等元信息。"""
    params = list(params or [])
    stmt = _prepare(engine, sql, params)
    with engine.begin() as conn:  # begin() 自动提交
        _use_database(conn, database, engine)
        if params:
            result = conn.exec_driver_sql(stmt, tuple(params))
        else:
            result = conn.exec_driver_sql(stmt)
        rowcount = result.rowcount
        info: Dict[str, Any] = {
            # 对齐 MySQL 语义：DDL 等无行数场景返回 0（部分驱动会给 -1）
            "affectedRows": rowcount if rowcount is not None and rowcount >= 0 else 0,
        }
        lastrowid = getattr(result, "lastrowid", None)
        if lastrowid is not None:
            info["insertId"] = lastrowid
        return info
