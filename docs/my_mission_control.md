# 8-Agent「Personal Panopticon」Mission Control（OpenClaw + Docker + Dash）完整備案

對應簡中工程落地手冊（弱化敘事、強化配置/清單/矩陣）：
- [docs/unmanned-company-playbook-zh-cn.md](docs/unmanned-company-playbook-zh-cn.md)

本文件把目前討論到的「Mission Control + 8 個並行個人 agent」方案完整落盤，目的不是做漂亮簡報，而是讓你可以直接按表施工：容器怎麼切、權限怎麼收、skills 怎麼治理、事件怎麼記錄、以及如何沿用 CN-IM 的 env→openclaw.json 生成模式做 per-agent 差異化。

關聯文件（本 repo）：
- 通用 Mission Control 設計： [docs/mission-control.md](docs/mission-control.md)
- Dash UI 原型： [MissionControl/app.py](MissionControl/app.py)
- Dash 樣式： [MissionControl/assets/styles.css](MissionControl/assets/styles.css)
- OpenClaw 設定範例（含 security / scheduler）： [examples/config.example.yaml](examples/config.example.yaml)
- CN-IM Docker 模板（env→openclaw.json）： [src/OpenClaw-Docker-CN-IM/README.md](src/OpenClaw-Docker-CN-IM/README.md)
- CN-IM env 範本： [src/OpenClaw-Docker-CN-IM/.env.example](src/OpenClaw-Docker-CN-IM/.env.example)
- CN-IM 參考設定： [src/OpenClaw-Docker-CN-IM/openclaw.json.example](src/OpenClaw-Docker-CN-IM/openclaw.json.example)

## 一句話目標
用「8 個目錄＝8 個獨立 agent」作為責任邊界與資料邊界：每個 agent 是隔離的 OpenClaw 容器（獨立 OpenClaw home、獨立工作區 volume、獨立工具白名單與心跳排程），由一個 Python 控制平面（Dash UI + API + WebSocket）統一派工、handoff、checkpoint、審計與通知。

## 核心設計原則（本次討論結論）
- 一 agent 一容器：避免共享狀態與技能污染，也避開「單一 OpenClaw 實例僅看到 agents/main」的限制風險。
- 即時感與可靠性分離：
	- REST/Redis Streams 負責任務一致性、可重放、去重。
	- WebSocket 只負責 live feed（斷線可降級，不影響任務完成）。
- 成本控制優先：心跳（13–17 分鐘抖動）不得觸發 LLM；只有 claim 到任務才允許推理。
- 審計與可回放優先：每次任務必須 artifact 化（結構化 JSON + 可讀 Markdown + sources 索引）。

## 元件與職責
### 1) Data plane：8 個 OpenClaw agent 容器
每個容器：
- 掛載獨立 OpenClaw home（例如 /root/.openclaw）以隔離 config / plugins / skills cache。
- 掛載獨立工作目錄到 /workspace（例如 host 的 ~/nox 對應一個 volume）。
- 容器內 gateway 服務固定使用 26216；host 端映射到不同 port（避免衝突）。
- 只啟用該角色需要的工具（browser/shell/外部 API）與最小權限。

### 2) Control plane：Mission Control（Dash + API + WS）
- UI（Dash）：沿用 [MissionControl/app.py](MissionControl/app.py) 的三欄布局（Agent roster / Kanban / Live feed）。
- API（建議 FastAPI）：任務 CRUD、指派、handoff、checkpoint、artifact 上傳/索引、稽核查詢。
- WS：推送 agent 狀態、任務事件、log 摘要到 live feed。

### 3) Async bus：Redis Streams（建議）
任務與事件的「單一真相來源」：
- task.assign：派工、handoff、review 請求
- event.log：append-only 稽核事件（狀態變更、產物上傳、工具使用摘要）

## 通訊協議（REST + Streams + WS 分工）
- 任務分配（可靠）：Mission Control 寫入 Redis Stream（例如 task.assign）。
- 任務領取（低成本）：agent 心跳只做 I/O：拉 stream、嘗試 claim lock、回報 alive。
- 任務執行（重型）：agent claim 成功後才呼叫 OpenClaw 推理與工具。
- 結果回傳（可靠）：agent 以 REST 上傳 artifacts，並寫入 event.log stream。
- 即時呈現（非可靠但即時）：agent wrapper 透過 WS 推送進度/摘要 log（可斷線重連、可降級）。

## 8 個 agent 的責任邊界（責任＝資料邊界）
- ~/nox：產品營運與 roadmap 建議（拉產品數據 + 交叉比對代碼變更 → 產出「該做什麼」）。
- ~/metrics：指標/歸因/異常偵測（包含 Goodhart guardrail：指出「指標被玩壞」的風險）。
- ~/email：收件匣分類、草擬回覆、追蹤待回（只允許郵件相關 API/IMAP/SMTP）。
- ~/growth：實驗設計、文案、漏斗（只允許 growth workspace 與分析讀取）。
- ~/trades：晨報/論點追蹤/資料整併（嚴格記錄來源與假設，避免「幻覺交易」）。
- ~/health：睡眠/訓練/恢復（以建議為主；高風險動作不自動執行）。
- ~/writing：長文/文件/內容產出（嚴格引用 artifacts，不直接憑空下結論）。
- ~/personal：訂閱、票據、待辦、行程（高風險動作預設進 Review）。

## Workspace「工作契約」（持久化與可審計）
每個 workspace（例如 ~/nox）固定子結構：
- inbox/：新任務與外部輸入
- outbox/：可交付成果（給人/給系統）
- artifacts/：任務產物（可檢索、可回放）
- state/：checkpoint、游標、上次處理位置
- sources/：原始資料快照與引用索引

每次任務至少產出：
- artifacts/<task_id>/artifact.json：結構化摘要（結論、假設、風險、下一步、引用）。
- artifacts/<task_id>/artifact.md：可閱讀版本。
- sources/<task_id>/：引用索引與（必要時）快照。

### Workspace 狀態全面測試（已落地）

新增測試腳本：
- [panopticon/tools/test_workspace_contract.py](panopticon/tools/test_workspace_contract.py)

嚴格模式（只檢查，不改目錄）：

```bash
python panopticon/tools/test_workspace_contract.py \
	--output panopticon/reports/workspace_contract_report_before.json
```

自動補齊缺失目錄後復測：

```bash
python panopticon/tools/test_workspace_contract.py \
	--auto-create \
	--output panopticon/reports/workspace_contract_report_after.json
```

覆蓋內容：
- 8 個 workspace 的固定子結構：`inbox/outbox/artifacts/state/sources`
- 每個子結構的可讀寫探針
- 最小任務生命週期探針：`inbox -> outbox -> artifacts -> state -> sources`

## Heartbeat 與成本控制（13–17 分鐘抖動）
- 心跳週期：每 agent 13–17 分鐘 jitter（避免同時喚醒）。
- 心跳技能嚴禁觸發 LLM：只做查 stream / 更新 last_seen / 檢查任務。
- 只有在「已 claim 任務」後才允許進入推理流程。

## Handoff（顯式交接）與一次性子代理（Phase 2）
- Handoff：任何跨域協作必須用 handoff 事件，內容包含：問題、必要上下文、引用 artifacts、期望輸出格式。
- 一次性子代理：由 Mission Control 用同一 OpenClaw image 啟動短 TTL 子容器（docker run --rm），只掛載該任務的臨時資料夾與最小權限；完成後把 artifacts 回寫主任務。

### 短期落地（已實作）：最小狀態機 + handoff 校驗 + 校驗事件流

已在 `mission_control_api/app/main.py` 的 `/v1/events` 接口增加最小治理能力：

- `task.status` 最小狀態機校驗與落表更新（`INBOX -> ASSIGNED -> IN PROGRESS -> REVIEW -> DONE`，允許 `REVIEW <-> IN PROGRESS` 與 `IN PROGRESS -> DONE`）。
- `task.handoff` 必填字段校驗：
	- `to`（目標 agent）
	- `problem`
	- `context`
	- `artifact_refs`（非空 list）
	- `expected_output`
	- `review_gate`（boolean）
- 校驗結果統一寫入 Redis 事件流：`event.validation`（包含 `accepted`、`errors`、`details`），便於 feed 審計與監控告警。

### Agent 事件上報接入（EVENT_HTTP_URL）

已在 `panopticon/templates/agent.env.tpl` 增加 agent 側上報欄位，供 wrapper/skills 直接接入：

- `EVENT_HTTP_URL`
- `EVENT_HTTP_TOKEN`
- `EVENT_HTTP_ENABLED`
- `EVENT_HTTP_TIMEOUT_SECONDS`
- `EVENT_HTTP_RETRY`
- `EVENT_REPORT_EVENT_TYPES=artifact.created,task.status,task.review.requested`

已在 `panopticon/tools/comprehensive_assessment.py` 增加對 `EVENT_HTTP_URL` 的可選驗證能力：

- 新增參數：`--event-http-url`、`--event-http-token`
- 在 `--run-lyric-case` 時，除寫入主 API 外，也會對 `EVENT_HTTP_URL` 驗證關鍵事件上報（`artifact.created` / `task.status` / `task.review.requested`）
- 報告中新增 `event_http_push` 結果，便於判斷 agent 側上報鏈路是否打通。

## 通知策略
- 當任務進入 Review / NeedsInput 時通知你。
- 通道先做低門檻（Email/Telegram/Slack 任一）；SMS/電話列為後續（成本與供應商綁定）。

## 安全護欄（避免「系統吞噬你」）
- ~/metrics 固定產出「指標風險報告」：可能的 Goodhart 行為、資料偏差、決策不確定性。
- ~/health、~/trades、~/personal 的高風險動作預設只能到 Review，不自動執行（避免自動交易/自動取消服務等不可逆操作）。
- 最小權限：每個 agent 只拿自己需要的 secrets、只掛自己 workspace、只開自己需要的工具。

## 8-agent 配置矩陣（建議配置，可依成本/品質調整）
說明：這裡用「模型層級」描述（small/medium/large），對應到 CN-IM 的 MODEL_ID / CONTEXT_WINDOW / MAX_TOKENS 等欄位；你可以替換成任意供應商與實際 model id。

| Agent | Workspace | 模型層級 | CONTEXT_WINDOW | MAX_TOKENS | Browser | Shell | Skills（global） | Skills（workspace） | 留存策略 |
|---|---|---|---:|---:|---|---|---|---|---|
| nox | ~/nox | medium | 64k–128k | 2k–4k | 讀取型 | 受限 | product-core, handoff, artifact | nox/* | artifacts 90d；sources 30d |
| metrics | ~/metrics | medium | 64k–128k | 2k–4k | 讀取型 | 受限 | metrics-core, anomaly, goodhart | metrics/* | artifacts 180d；sources 90d |
| email | ~/email | small | 16k–64k | 1k–2k | 否 | 否 | email-core, redact, artifact | email/* | artifacts 30–90d；sources 7–30d |
| growth | ~/growth | medium | 64k–128k | 2k–4k | 讀取型 | 受限 | growth-core, experiment | growth/* | artifacts 180d；sources 30–90d |
| trades | ~/trades | medium | 64k–128k | 1k–2k | 讀取型 | 否 | trades-core, citations, risk | trades/* | artifacts 365d；sources 180d |
| health | ~/health | small | 16k–64k | 1k–2k | 否 | 否 | health-core, safety, artifact | health/* | artifacts 180d；sources 30d |
| writing | ~/writing | large | 128k+ | 4k–8k | 讀取型 | 受限 | writing-core, outline, cite | writing/* | artifacts 365d；sources 180d |
| personal | ~/personal | small | 16k–64k | 1k–2k | 視需求 | 否 | personal-core, review-gate, redact | personal/* | artifacts 180d；sources 30–90d |

Browser/Shell 權限建議：
- 「讀取型 browser」：只允許抓取白名單網域與下載到 sources/；不允許任意上傳。
- 「受限 shell」：只允許 workspace 內的特定命令（例如格式化、統計、轉檔）；禁止網路掃描、系統管理。

## skills：global + workspace 雙層策略（治理規範）
目標：讓「通用能力」與「角色能力」解耦，並且可審計、可灰度、可回退。

### 1) Global skills（共用，偏平台能力）
特性：
- 不含角色業務邏輯；偏通用（artifact 序列化、redaction、handoff、事件上報、格式檢查）。
- 版本化與白名單化：每個 agent 只允許一組 allowlist。

建議 global skills 類型：
- artifact：產出 artifact.json / artifact.md、schema 檢查
- handoff：標準交接事件格式
- redact：PII/secrets 去敏
- event-reporter：寫入 event.log / 呼叫 Mission Control API

### 2) Workspace skills（角色特化）
特性：
- 每個 workspace 自己維護（nox/*、metrics/*…），只能讀寫自己的 workspace。
- 明確宣告 I/O：可用哪些外部 API、可讀哪些資料夾、可寫哪些輸出目錄。

### 3) 技能裝載順序（建議）
- 先載入 global skills，再載入 workspace skills；同名衝突以 workspace 為準（方便角色覆寫，但需審核）。

## 對照 CN-IM 模板：需新增/擴充的 env/config 欄位
CN-IM 既有欄位（可直接沿用）：
- MODEL_ID / BASE_URL / API_KEY / API_PROTOCOL
- CONTEXT_WINDOW / MAX_TOKENS
- WORKSPACE
- OPENCLAW_DATA_DIR
- OPENCLAW_GATEWAY_*（token/port 等，依模板內容）

為了支援「多 agent per-container 差異化」與「Mission Control 整合」，建議新增：
- AGENT_SLUG：nox/metrics/email/...（用於命名、事件上報、log 標籤）
- AGENT_ROLE：可讀的人類角色描述（可選）
- AGENT_HOST_PORT：對外映射 port（例如 26216→18xxx）
- OPENCLAW_HOME_DIR：容器內 OpenClaw home（例如 /root/.openclaw）
- WORKSPACE_DIR：容器內 workspace 掛載點（例如 /workspace）
- GLOBAL_SKILLS_DIR：global skills 掛載路徑（例如 /skills/global）
- WORKSPACE_SKILLS_DIR：workspace skills 掛載路徑（例如 /workspace/skills）
- SKILLS_ALLOWLIST：允許載入的 skills 清單（逗號分隔）
- ENABLE_BROWSER：0/1
- ENABLE_SHELL：0/1
- REDACTION_MODE：off/basic/strict（去敏強度）
- EVENT_HTTP_URL：Mission Control API endpoint（artifact 上報/狀態回報）
- EVENT_WS_URL：Mission Control WS endpoint（live feed）
- HEARTBEAT_MINUTES_MIN / HEARTBEAT_MINUTES_MAX：抖動範圍
- RETENTION_ARTIFACT_DAYS / RETENTION_SOURCES_DAYS：留存

對照 CN-IM 生成策略（重點提醒）：
- CN-IM 的 [src/OpenClaw-Docker-CN-IM/init.sh](src/OpenClaw-Docker-CN-IM/init.sh) 是「若 openclaw.json 不存在才由 env 生成」。
- 多 agent 模式下建議每個容器一份獨立 OPENCLAW_DATA_DIR（或獨立掛載的 OpenClaw home），避免共用造成設定與技能污染。

## env 管理兩種路線（都可行）
### 路線 A：每個 agent 一份 env_file（最清楚、最好審計）
- 優點：差異可讀、最不容易寫錯。
- 缺點：檔案較多。

### 路線 B：單一 .env 用前綴（AGENT_NOX_* / AGENT_METRICS_*）
- 優點：集中管理。
- 缺點：需要一段「前綴轉換」腳本把 env 映射為 CN-IM 期待的欄位。

## 漸進上線（風險分層）
- Phase 1：只開 email + writing + personal（低風險、高回報）。
- Phase 2：加入 nox + metrics + growth。
- Phase 3：最後加入 trades + health（風險最高、審計要求最高）。

## 驗證清單（可作為 Done Definition）
- 並行性：8 個容器同時在線，彼此資料完全隔離（只能讀寫自己的 /workspace）。
- 成本：24 小時內 heartbeat 不觸發推理；只有有任務才進 LLM。
- 一致性：任務不重複被兩個 agent claim（lock + idempotency）。
- 可追溯：每個任務都能回放「指派 → 執行 → artifacts → review」。
- 降級：WS 斷線時系統仍可用（少即時感，不影響任務完成）。

## 已落地現況（本 repo）
- Dash UI 原型已存在於 [MissionControl/app.py](MissionControl/app.py) 並可啟動；Dash 啟動方式已採用相容的新入口（run）。
- 通用 Mission Control 架構說明已在 [docs/mission-control.md](docs/mission-control.md)。

## 全面評估落地（可執行）

已新增綜合評估腳本：
- [panopticon/tools/comprehensive_assessment.py](panopticon/tools/comprehensive_assessment.py)

### 基本用法（只讀評估）

```bash
python panopticon/tools/comprehensive_assessment.py \
	--api-base http://127.0.0.1:18910 \
	--ui-base http://127.0.0.1:18920 \
	--feed-limit 800 \
	--output panopticon/reports/assessment.json
```

該命令會同時輸出：
- 協作評分（Mission Control API/UI/事件指標）
- workspace 狀態測試（`inbox/outbox/artifacts/state/sources`）

### 協作案例演練（寫入任務/事件）

```bash
python panopticon/tools/comprehensive_assessment.py \
	--run-lyric-case \
	--feed-limit 800 \
	--workspace-auto-create \
	--output panopticon/reports/assessment_lyric_case.json
```

### 指標與評分（腳本內建）

- task_success_rate_pct（權重 20%）：DONE / 全部任務
- lifecycle_coverage_pct（權重 20%）：任務是否可在 feed 中找到事件證據
- handoff_completeness_pct（權重 15%）：handoff 關鍵字段完整率
- heartbeat_continuity_pct（權重 10%）：窗口內心跳覆蓋率
- feed_freshness_sec（權重 10%，越小越好）：最新事件新鮮度
- probe_event_latency_sec（權重 15%，越小越好）：探針事件寫入到 feed 可見延遲
- review_gate_bypass_rate_pct（權重 10%，越小越好）：高風險任務繞過 Review 比例

評分輸出：
- 終端輸出人可讀摘要
- `--output` 生成 JSON 報告（便於後續儀表板或 CI 對接）
- `--feed-limit` 控制 feed 採樣深度（建議 500~1000，避免 lifecycle/handoff 指標低估）
- `--workspace-auto-create` 在 workspace 測試時自動補齊缺失目錄
- `--skip-workspace-contract` 只跑協作評分，不跑 workspace 狀態測試
