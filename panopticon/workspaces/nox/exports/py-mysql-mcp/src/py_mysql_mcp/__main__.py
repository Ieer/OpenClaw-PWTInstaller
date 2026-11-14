"""入口：加载配置 → 建连接池 → 启动 MCP 服务 → 优雅关闭。

``python -m py_mysql_mcp``
"""

from __future__ import annotations

import logging
import signal
import sys

from .config import ConfigError, load_config
from .db import close_pool, create_pool
from .server import run


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("py_mysql_mcp")

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Fatal config error: %s", exc)
        return 1

    engine = create_pool(config)
    logger.info(
        "MySQL pool created: %s@%s:%s%s (poolSize=%s)",
        config.mysql_user,
        config.mysql_host,
        config.mysql_port,
        f"/{config.mysql_database}" if config.mysql_database else "",
        config.pool_size,
    )

    def _shutdown(signum, _frame):  # noqa: ANN001
        logger.info("Received signal %s, disposing pool...", signum)
        close_pool(engine)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        run(config, engine)
    finally:
        close_pool(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
