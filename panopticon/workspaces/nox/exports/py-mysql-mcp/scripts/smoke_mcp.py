"""端到端冒烟测试：启动本服务（SQLite 演示库），用 MCP Streamable HTTP 客户端调用工具。

用法：
    DATABASE_URL=sqlite:///./smoke.db MCP_HTTP_PORT=3111 python -m py_mysql_mcp &
    python scripts/smoke_mcp.py http://127.0.0.1:3111/mcp
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main(url: str) -> None:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("tools:", sorted(t.name for t in tools.tools))

            async def call(name, args):
                res = await session.call_tool(name, args)
                print(f"\n[{name}] {res.content[0].text}")
                return res

            await call("mysql_execute", {"sql": "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)"})
            await call("mysql_execute", {"sql": "INSERT INTO users (name, age) VALUES (?, ?)", "params": ["Alice", 30]})
            await call("mysql_execute", {"sql": "INSERT INTO users (name, age) VALUES (?, ?)", "params": ["机械键盘", 17]})
            await call("mysql_query", {"sql": "SELECT id, name, age FROM users WHERE age > ? ORDER BY id", "params": [18]})
            await call("mysql_query", {"sql": "SELECT COUNT(*) AS n FROM users"})
            # 只读守卫（本进程未开只读，这里演示正常写入；只读校验由单元测试覆盖）


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3111/mcp"))
