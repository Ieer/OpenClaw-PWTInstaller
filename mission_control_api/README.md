# Mission Control API (WIP)

最小可跑的 Mission Control 後端骨架：
- REST：任務看板/留言/活動流
- WS：即時事件流（由 Redis Streams 提供）
- 儲存：Postgres（啟用 pgvector extension）

> 這是工程落地起點：先把資料面/事件面跑起來，再讓 MissionControl Dash UI 改為吃 API。
