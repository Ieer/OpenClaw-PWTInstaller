# Mission Control API

路徑口徑（與主入口同步）：
- 主推路線是 `8-Agent Panopticon + Mission Control` 平台化編排。
- 單 Agent 命令列安裝器屬次要路線。
- 根目錄 `docker-compose.yml` 單容器路徑屬實驗性方案（非主推、非生產預設）。

若需完整運行入口與部署說明，優先參考：
- [../README.md](../README.md)
- [../panopticon/README.md](../panopticon/README.md)

可運行的 Mission Control 後端實作，目前已提供：
- REST：健康檢查、任務看板、留言、活動流、skills mapping、usage 聚合
- WS：即時事件流（由 Redis Streams 提供）
- Chat：同源 HTTP / WebSocket 代理，可對接各 agent 的 Control UI / Chat
- 儲存：Postgres（啟用 pgvector extension，並預留記憶相關表）

此服務已接入 Panopticon 編排，並由 `MissionControl` Dash UI 直接調用。

## Schema 迁移与初始化策略

Mission Control 数据层已切换为 **Alembic 单轨迁移**：

- 应用容器启动时先执行 `alembic upgrade head`，成功后才启动 API。
- 应用代码不再在 `startup` 事件里执行兜底 `CREATE TABLE/INDEX`。
- Postgres 初始化目录中的 legacy SQL 不再作为默认 schema 来源。

本地开发常用命令：

```bash
# 在 mission_control_api 目录
alembic upgrade head

# 生成新迁移（手工调整后提交）
alembic revision -m "your migration message"

# 回退一步
alembic downgrade -1
```

约束建议：

- 所有 schema 变更必须通过 Alembic 版本脚本提交。
- `app/main.py` 禁止再新增运行期 DDL 兜底逻辑。
- 迁移脚本需保持可重复执行（幂等）并包含 downgrade。

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
