# Mission Control API (WIP)

最小可跑的 Mission Control 後端骨架：
- REST：任務看板/留言/活動流
- WS：即時事件流（由 Redis Streams 提供）
- 儲存：Postgres（啟用 pgvector extension）

> 這是工程落地起點：先把資料面/事件面跑起來，再讓 MissionControl Dash UI 改為吃 API。

## Skills 映射更新（逐項失敗明細）

`PATCH /v1/skills/mappings` 現在支援「部分成功」語義：

- 可執行的映射會正常寫入/刪除。
- 無法執行的映射不會中斷整批請求，會回傳到 `failed` 陣列。

回傳欄位：

- `updated`: 成功套用的映射變更數。
- `affected_agents`: 實際被處理的 agent 清單。
- `restart_hint`: 生效提示。
- `failed`: 逐項失敗明細，元素格式：
	- `action`: `add` 或 `remove`
	- `agent_slug`
	- `skill_slug`
	- `reason`

`reason` 目前可能值：

- `unknown_agent`
- `unknown_global_skill`
- `already_mapped`
- `not_mapped`
