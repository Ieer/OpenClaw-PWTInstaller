# py-mysql-mcp

基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的 MySQL 数据库访问服务（**Python 版**，`ts-mysql-mcp` 的重构实现）。大模型可通过标准化的工具接口对 MySQL 执行查询、增删改、表结构查看等操作。

## 与 TS 版的差异（重构要点）

参考《FastAPI 前期用 SQLite 做 Demo → 后期迁移生产库》一篇的工程实践，本实现在忠实对齐 TS 版工具契约（4 个工具、`?` 占位符、只读守卫）的同时，做了以下强化：

| 维度 | TS 版 | 本 Python 版 |
|------|-------|--------------|
| 依赖 | mysql2 + zod | SQLAlchemy 2.0 + PyMySQL + MCP SDK |
| 连接管理 | mysql2 连接池 | SQLAlchemy Engine 连接池（`pool_size`/`pool_pre_ping`/`pool_recycle`） |
| 换库成本 | 写死 MySQL 驱动 | 执行层走 SQLAlchemy 方言，`DATABASE_URL` 一处切换；占位符按 `paramstyle` 自适应 |
| 参数安全 | `?` 占位符 | `?` 占位符 + 词法感知转换（跳过字符串/注释/反引号中的 `?`）+ 占位符数量校验 |
| 标识符 | 正则白名单 | 同样白名单校验（`sanitize_identifier`） |
| 只读守卫 | 首关键词判断 | 同上，并忽略前导注释 |
| 配置 | env + dotenv | 同左，dataclass 强类型 + 启动即校验 |
| 可测性 | 无 | 覆盖 config / guard / 占位符 / 集成（SQLite）的 pytest 用例 |

> 说明：本工具的本质是「执行用户传入的任意 SQL」，因此并不适用 ORM 实体映射；原文「参数化绑定、凭据环境变量化、配置集中一处」的原则在此落地为 **SQLAlchemy 连接/方言层 + 严格参数绑定 + `DATABASE_URL` 单点切换**。

## 工具

| 工具 | 用途 | 入参 | 只读模式 |
|------|------|------|----------|
| `mysql_query` | 执行返回结果集的语句（SELECT） | `sql`, `params?`, `database?` | 仅允许 SELECT/SHOW/DESCRIBE/EXPLAIN |
| `mysql_execute` | 执行 DDL（CREATE/ALTER/DROP）和 DML（INSERT/UPDATE/DELETE） | `sql`, `params?`, `database?` | 完全禁用 |
| `mysql_list` | 列出所有数据库或指定库的表 | `type: "databases"\|"tables"`, `database?` | 允许 |
| `mysql_describe` | 查看表的列定义 | `table`, `database?` | 允许 |

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env      # 填写你的 MySQL 连接信息
```

## 运行

```bash
python -m py_mysql_mcp
# 或（安装后）
py-mysql-mcp
```

服务启动后监听 `http://127.0.0.1:3000/mcp`，MCP 端点为 `/mcp`（支持 POST / GET / DELETE）。

开发/测试：

```bash
pip install -e ".[dev]"
pytest
```

## 配置（.env）

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database
MYSQL_POOL_SIZE=10
MYSQL_READ_ONLY=false
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=3000
```

可选 `DATABASE_URL` 覆盖完整连接串（便于本地用 SQLite 演示 / 后续换库）：

```env
DATABASE_URL=sqlite:///./demo.db
```

## 客户端配置（Streamable HTTP）

```json
{
  "mcpServers": {
    "mysql": {
      "url": "http://127.0.0.1:3000/mcp"
    }
  }
}
```

## 调用示例

查询数据：

```json
{ "sql": "SELECT id, name, email FROM users WHERE age > ? ORDER BY id LIMIT ?", "params": [18, 10] }
```

插入数据：

```json
{ "sql": "INSERT INTO users (name, email) VALUES (?, ?)", "params": ["Alice", "alice@example.com"] }
```

列出数据库 / 查看表结构：

```json
{ "type": "databases" }
{ "table": "users" }
```

## 安全边界

这是本地开发示例，默认允许写入，HTTP 服务没有独立的客户端鉴权。只在可信本机使用，不要绑定公网或将端口转发给不可信客户端；当前测试使用 SQLite，尚未验证真实 MySQL 部署。

- **凭据管理**：所有 MySQL 连接信息通过环境变量注入，`.env` 已加入 `.gitignore`。
- **参数绑定**：`params` 通过 `?` 占位符绑定；表名/库名等标识符通过白名单校验。但调用者提供的 `sql` 仍是任意 SQL，并不是 SQL 沙箱。
- **只读模式**：`MYSQL_READ_ONLY=true` 禁用 `mysql_execute`，并检查查询的首关键词。这只是辅助检查，不能保证语句无副作用，也不能代替数据库权限控制。读取用途应使用专门的最小权限账号，撤销写入、文件和管理权限，不使用 `root`。
- **连接池限制**：`MYSQL_POOL_SIZE` 限制最大连接数，配合 `pool_pre_ping` 防止失效连接。
- **错误信息**：返回结构化 `{success:false, error:{message, errno, code}}`，但驱动错误和 SQL 可能进入响应或日志；尚未实现完整脱敏。不要把凭据放进 SQL，不对不可信客户端开放日志和服务。

## 目录结构

```
py-mysql-mcp/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── src/py_mysql_mcp/
│   ├── __init__.py
│   ├── __main__.py        # 入口：配置 → 连接池 → 服务 → 优雅关闭
│   ├── config.py          # 环境变量读取与校验
│   ├── db.py              # SQLAlchemy Engine + 参数化执行
│   ├── guard.py           # 只读守卫 + 标识符白名单
│   ├── sqlparams.py       # ? 占位符 → 驱动 paramstyle 转换
│   ├── server.py          # FastMCP 装配（Streamable HTTP）
│   └── tools/
│       ├── __init__.py    # 工具注册总入口
│       ├── _shared.py     # 统一成功/错误返回
│       ├── query.py       # mysql_query
│       ├── execute.py     # mysql_execute
│       ├── list_tables.py # mysql_list
│       └── describe.py    # mysql_describe
└── tests/
    ├── test_config.py
    ├── test_guard.py
    ├── test_sqlparams.py
    ├── test_db_integration.py
    └── test_server.py
```

## License

MIT
