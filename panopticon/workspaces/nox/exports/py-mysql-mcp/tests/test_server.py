"""校验 FastMCP 服务装配：注册了 4 个工具且名称正确。"""

import pytest

from py_mysql_mcp.config import AppConfig
from py_mysql_mcp.db import create_pool
from py_mysql_mcp.server import build_server


@pytest.fixture()
def config(tmp_path):
    return AppConfig(
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="root",
        mysql_password="",
        mysql_database=None,
        pool_size=5,
        read_only=True,
        http_host="127.0.0.1",
        http_port=3000,
        database_url=f"sqlite:///{tmp_path/'x.db'}",
    )


@pytest.mark.anyio
async def test_tools_registered(config):
    engine = create_pool(config)
    mcp = build_server(config, engine)
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert {"mysql_query", "mysql_execute", "mysql_list", "mysql_describe"} <= names
    engine.dispose()


@pytest.fixture()
def anyio_backend():
    return "asyncio"
