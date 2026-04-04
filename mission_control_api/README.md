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
- REST（knowledge）：知識原始資料來源登記、知識單元治理、驗證、resolve、回流統計
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

## 知識原始資料（普通 U 盤推薦）

Mission Control API 支援把「原始資料」從掛載目錄登記到 `knowledge_sources`：

- `POST /v1/knowledge/sources/import`：按相對路徑導入單個文件
- `POST /v1/knowledge/sources/scan`：批量掃描目錄並入庫
- `GET /v1/knowledge/sources`：列表查詢
- `GET /v1/knowledge/sources/{id}`：單條詳情
- `POST /v1/knowledge/sources/{source_id}/chunk`：自動切片為 `knowledge_units`
	- 已支援：`txt/md/rst/csv/json/yaml/yml/log/pdf/docx/pptx/xlsx`
	- OCR 第一版已支援：`png/jpg/jpeg/webp` 圖片 OCR、掃描 PDF OCR fallback（Tesseract）
	- OCR 運行參數：`ocr_enabled`、`ocr_languages`、`max_pdf_pages`

知識治理（本次新增）：

- `POST /v1/knowledge/units`：建立知識單元（切片結果）
- `GET /v1/knowledge/units`：按來源/agent/risk/status 查詢
- `POST /v1/knowledge/validations`：寫入驗證記錄（誰驗證、何時過期）
- `GET /v1/knowledge/validations`：查詢驗證歷史
- `GET /v1/knowledge/validation-policy`：查看各風險級別必檢規則
- `PUT /v1/knowledge/validation-policy/{risk_level}`：更新某風險級別必檢規則
	- 支援 `strict_mode`：缺失關鍵 validation 欄位時直接拒絕
- `GET /v1/knowledge/validation-policy/bundles`：查看 policy bundle（策略版本實體）
- `POST /v1/knowledge/validation-policy/bundles`：建立或覆蓋某個 bundle
- `PUT /v1/knowledge/validation-policy/bundles/{bundle_id}`：更新 bundle
- `GET /v1/knowledge/validation-policy/rules`：查看 bundle 下的動態規則
- `POST /v1/knowledge/validation-policy/rules`：建立或覆蓋動態規則
- `PUT /v1/knowledge/validation-policy/rules/{rule_id}`：更新動態規則
- `GET /v1/knowledge/validation-policy/rollouts`：查看 bundle rollout 規則
- `POST /v1/knowledge/validation-policy/rollouts`：建立或覆蓋 rollout
- `PUT /v1/knowledge/validation-policy/rollouts/{rollout_id}`：更新 rollout
	- 同優先級 rollout 目前採用「最近更新優先」作為確定性 tie-breaker，避免舊配置搶占新發布
	- `task_pattern` 目前採用 `*` 通配符語義（例如 `*incident*`），不是原生正則表達式
- `GET /v1/knowledge/resolve/ranking-profiles`：查看 hybrid resolve ranking profile
- `POST /v1/knowledge/resolve/ranking-profiles`：建立或覆蓋 ranking profile
- `PUT /v1/knowledge/resolve/ranking-profiles/{profile_id}`：更新 ranking profile
- `POST /v1/knowledge/resolve`：按任務 + agent + risk 生成知識包
	- 可選參數：`include_rejected=true`（調試回傳拒絕清單）
	- 可選參數：`retrieval_mode=hybrid|semantic`，將向量召回接入 resolve 候選層
	- 可選參數：`ranking_profile`、`min_semantic_similarity`、`min_score`，用於 hybrid resolve 第二階段排序與閾值控制
- `GET /v1/knowledge/resolve/audits`：查看 resolve 審計（命中來源、拒絕原因）
- `GET /v1/knowledge/resolve/rejections/summary`：統計拒絕原因分佈
- `GET /v1/knowledge/resolve/metrics`：監控 resolve 命中率、拒絕率、過期拒絕量與 Top 拒絕原因
	- 已補充：`requests_without_hits`、`requests_without_rejections`、`resolve_rejection_rate`、`unit_selection_rate`、`expired_rejection_rate`
	- 已補充：`risk_breakdown[]`（按 requested risk level 聚合命中/拒絕情況）
	- 亦包含 OCR 聚合觀測：`ocr_fallback_count`、`ocr_failure_count`、`ocr_failure_rate`、`ocr_page_truncation_count`
- `GET /v1/knowledge/validation-policy/change-events`：查看 bundle / rule / rollout / ranking profile 變更事件
- `GET /v1/knowledge/validation-policy/observability/summary`：查看 bundle / rollout / ranking profile 使用觀測摘要
- `POST /v1/knowledge/validation-policy/bundles/{bundle_id}/rollback`：按最近變更快照執行 bundle soft rollback
- `POST /v1/knowledge/validation-policy/rollouts/{rollout_id}/rollback`：按最近變更快照執行 rollout soft rollback
- `POST /v1/knowledge/feedback`：回流事件（usage/conflict/invalidation/promotion）
- `GET /v1/knowledge/feedback/summary`：回流聚合統計
- `POST /v1/knowledge/units/{unit_id}/lifecycle`：顯式執行 lifecycle action（promote/demote/invalidate/reactivate/archive/supersede）
- `GET /v1/knowledge/units/{unit_id}/lifecycle-events`：查看 lifecycle 事件流

建議的 P0 回歸命令（可重複執行）：

- `bash tools/verify_knowledge_p0_regression.sh`

OCR 專項驗收命令：

- `bash tools/verify_knowledge_ocr_flow.sh`

動態策略 / rollout / lifecycle 驗收命令：

- `bash tools/verify_knowledge_dynamic_policy_rollout_flow.sh`

策略治理 / ranking profile / rollback 驗收命令：

- `bash tools/verify_knowledge_policy_governance_flow.sh`

Hybrid resolve 基準命令：

- `bash tools/benchmark_knowledge_hybrid_resolve.sh`

Embedding 配置（P2 第 2 步）：

- `MC_KNOWLEDGE_EMBEDDING_ENABLED`
- `MC_KNOWLEDGE_EMBEDDING_MODEL`
- `MC_KNOWLEDGE_EMBEDDING_BASE_URL`
- `MC_KNOWLEDGE_EMBEDDING_API_KEY`
- `MC_KNOWLEDGE_EMBEDDING_API_PROTOCOL`（目前支援 OpenAI-compatible embeddings）
- `MC_KNOWLEDGE_EMBEDDING_DIMENSIONS`（可選；提供時用作模型維度校驗，不提供時以 provider 實際返回維度為準）
- `MC_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS`

目前行為：

- `POST /v1/knowledge/sources/{source_id}/chunk` 在建立新 `knowledge_units` 後，會在 embedding 啟用時同步寫入 `knowledge_unit_embeddings`
- `POST /v1/knowledge/search` 會先生成查詢向量，再按 `embedding_model + embedding_dimensions` 過濾到同一向量分區後執行 cosine search
- `POST /v1/knowledge/search` 已支援 `source_type` 與 `require_approved_validation` 過濾，用於降低高風險場景的噪聲召回
- embedding 請求失敗不回滾已建立的 `knowledge_units`，會將失敗狀態寫回 `unit/source meta`
- `knowledge_unit_embeddings.embedding` 已改為非固定維度 `vector`，可容納不同模型的 1024 / 1536 等維度；實際維度記錄在 `embedding_dimensions`
- 最小 search API 目前要求查詢 runtime model 與目標分區一致；若 `embedding_model` / `embedding_dimensions` 與查詢向量不一致會直接拒絕，避免跨模型誤召回
- `POST /v1/knowledge/resolve` 現已支援最小 hybrid resolve：`retrieval_mode=hybrid` 時會把 lexical 候選與 semantic 候選合併後再套用現有 validation policy / audit 流程
- `POST /v1/knowledge/resolve` 現已支援 dynamic validation policy：會先做 bundle / rollout 選擇，再嘗試命中動態 rule，未命中時回退到原有 risk-level default policy
- `POST /v1/knowledge/resolve` 現已支援 hybrid resolve 第二階段排序：可透過資料庫中的 `ranking_profile`、`min_semantic_similarity`、`min_score` 控制排序和閾值
- ranking profile 已由硬編碼檔位改為資料模型，可獨立管理權重與閾值預設；resolve 審計會同步記錄 `ranking_profile` 與 `ranking_profile_weights`
- policy bundle / rule / rollout / ranking profile 的 create/update 已接入 change event；rollback 目前為 soft rollback，依最近事件快照恢復，若無前態則會安全禁用
- `GET /v1/knowledge/validation-policy/observability/summary` 會基於 resolve audit 中的 `policy_metadata` 聚合 bundle / rollout / ranking profile 命中情況，用於發布觀測
- lifecycle 第一版已落地：knowledge unit 支援 `preferred / deprecated / inactive / archived / superseded` 等 stage，且 promotion / invalidation feedback 會同步寫入 lifecycle event

向量索引策略（P2 最小版）：

- 通用過濾索引：`(embedding_model, embedding_dimensions, updated_at DESC)`
- 常用模型局部 HNSW：目前為 `bge-m3:latest + 1024 維` 建立 cosine partial index
- 常用模型局部 HNSW 模板：已預留 `mxbai-embed-large:latest + 1024`、`nomic-embed-text:latest + 768`、`all-minilm:latest + 384`
- 若後續新增常用模型，建議按 `embedding_model + embedding_dimensions` 再各自補 partial HNSW/IVFFlat index

資料模型補充：

- `knowledge_units`
- `knowledge_unit_embeddings`（P2 第一步基礎設施：知識單元專用向量表，不與 `memory_chunks` 混用）
- `knowledge_validations`
- `knowledge_feedback_events`
- `knowledge_validation_policies`
- `knowledge_resolve_audits`

對應環境變量：

- `MC_KNOWLEDGE_RAW_SOURCES_DIR`（預設 `/data/knowledge-sources`）

Panopticon 內建掛載建議：

- host: `${PANOPTICON_USB_HOST_PATH}/${PANOPTICON_KNOWLEDGE_USB_SUBDIR}`
- container: `/data/knowledge-sources`
