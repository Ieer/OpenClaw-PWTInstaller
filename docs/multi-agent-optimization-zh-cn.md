# 多 Agent 优化与执行试点

## 范围与状态

本轮保留 8 个独立 Agent 在线，不合并生产 Gateway、不迁移主机、不改变模型和原生聊天并发。以下是源码能力，部署状态应以实际镜像和环境变量核对，不能仅凭仓库文件判断。

| 优先级 | 已实现能力 | 边界 |
| --- | --- | --- |
| P0 | 任务事务行锁、可选请求幂等、事件 outbox、托管队列租约与预算 | 不自动接管原生聊天、cron、OCR 和备份 |
| P1 | 查询向量 TTL 缓存、同请求合并、并发限制和观测指标 | 不缓存知识包、权限、validation 或最终判断；不承诺常驻内存下降 |
| P2 | LangGraph 周报、SQLite 检查点、队列草稿 worker 与人工审查 | 不自动接管原生聊天，不发送邮件、交易或执行生产变更 |

上游参考：[OpenClaw](https://github.com/openclaw/openclaw)、[LangGraph](https://github.com/langchain-ai/langgraph)、[CrewAI](https://github.com/crewAIInc/crewAI)、[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)。当前不引入第二套知识库或更换控制台。

## P0：可靠写入与投递

任务领取、完成、审查以及 `task.handoff` / `task.status` 在读取当前状态时锁定任务行。竞争请求等待前一事务结束再检查归属。`force` 仍保留既有授权语义，不能当作普通 worker 的默认参数。

下列写接口可使用 `Idempotency-Key`：创建任务、领取、完成、审查、评论和 `/v1/events`。重试必须使用相同键和相同 JSON 内容；键按接口及任务隔离，不同内容返回 409。防重记录与业务更新同事务提交。未传键保持旧接口行为，不保证重复提交无副作用。

outbox 只登记新写入的业务事件，不回放历史数据。成功投递记录保留一天，失败记录继续保留并退避重试；轮询 2 秒、每批最多 50 条、退避最多 300 秒、归档清理最多每分钟一次。PostgreSQL 提交后 Redis 故障不会撤销已提交任务。

投递语义是至少一次：Redis 已写入但数据库确认失败时可能重投。消费者必须按事件 `id` 去重。`event.validation` 仍是瞬时反馈，不属于持久业务事件。邮件、交易和其他外部动作必须在适配器或下游实现独立幂等与人工授权；不能从 outbox 推导出外部动作恰好一次。

观察 `GET /v1/observability/outbox` 的 `pending`、`oldest_created_at`、`max_attempts`。积压持续增长应检查 Redis 和数据库，不删除未投递记录来掩盖故障。

## P0：托管队列

设置 `MC_EXECUTION_ENABLED=1` 才启用；建议先接单个草稿任务，并配置非空 `MC_AUTH_TOKEN`。共享控制面 token 是受信任调用方边界，不是每个 agent 的独立身份授权。

| 设置 | 默认值 | 含义 |
| --- | --- | --- |
| `MC_EXECUTION_GLOBAL_LIMIT` | 4 | 所有托管 RUNNING 作业合计 |
| `MC_EXECUTION_MAIN_LIMIT` | 4 | main 类别上限 |
| `MC_EXECUTION_SUBTASK_LIMIT` | 2 | subtask 类别上限 |
| `MC_EXECUTION_MAINTENANCE_LIMIT` | 1 | maintenance 类别上限 |
| `MC_EXECUTION_AGENT_LIMIT` | 2 | 单角色所有类别合计 |
| `MC_EXECUTION_LEASE_SECONDS` | 60 | 默认续租窗口 |
| `MC_EXECUTION_PROVIDER_RPM` | 20 | 同 provider 每分钟作业领取次数 |
| `MC_EXECUTION_PROVIDER_TPM` | 60000 | 同 provider 每分钟申报 token 预留量 |

类别额度不是互相独立的总预算，所有类别仍受 global 限额约束。PostgreSQL 事务 advisory lock 串行化预算决策，因此多 API worker 不能分别耗用一套预算。它不是跨数据库调度器。

1. `POST /v1/execution/jobs`：提交 `agent_slug`、`idempotency_key`、`kind`、`payload`；可附 `provider`、`estimated_tokens`、`priority`、`timeout_seconds`、`max_attempts`。
2. `POST /v1/execution/claim`：worker 提交 `agent_slug`、`worker_id`、`kind`。额度不足或无作业时返回 `{"job": null}`。小 priority 优先，同优先级按创建时间。
3. 领取响应包含 `lease_token`；worker 在窗口内调用 `/v1/execution/jobs/{id}/heartbeat` 续租。总运行期限不可通过续租延长。
4. `/v1/execution/jobs/{id}/finish` 接收令牌、`success`、`result`、`retry`、`error`。超期或旧 worker 的写入返回 409。
5. `GET /v1/execution/jobs/{id}` 查看状态，不返回租约令牌；`GET /v1/execution/summary` 查看数量、过期租约与预算。

领取时回收过期 RUNNING 作业：还有尝试次数则延迟 30 秒排队，否则 FAILED。失败重试有退避，总次数默认 3、最多 5。完成响应丢失时先查询作业状态，不重新执行业务动作。涉及不可安全重放的工作必须设 `max_attempts=1`，由操作员核对实际结果后恢复。

provider 和 token 是调用方申报的预留预算，不是模型计费实测；一个作业内部若多次调用模型，worker 必须拆分或完整申报，并对实际供应商额度另行限流。未标 provider 的非模型任务不占供应商预算。此能力不能限制绕过队列的聊天或脚本。

标明 provider 的作业必须申报大于零且不超过每分钟预算的 token 数，否则返回 422，避免作业永久不可领取。

payload/result 上限 32 KiB，长材料放产物目录，仅传引用。新队列不依赖任务看板的状态，不会把旧 `IN PROGRESS` 卡片自动当作活跃租约。

## P1：查询向量缓存

`MC_KNOWLEDGE_EMBEDDING_CACHE_TTL_SECONDS=60`，设为 0 停止存储缓存项。同请求合并与并发限制仍存在。每个 API 进程最多 128 项缓存、128 项在途键，同时至多 2 个受该缓存包装的 embedding 请求执行。

键为查询、角色、风险、完整 embedding 运行配置及 `MC_KNOWLEDGE_EMBEDDING_CACHE_REVISION` 的 SHA-256，不记录查询或凭据明文。变更模型、端点、凭据或版本标记产生新键。返回值拷贝隔离，失败不缓存，单个等待者取消不取消其他等待者。

只复用查询向量。每次 resolve 仍重新查资料与动态策略，执行权限过滤、validation、排序并写审计。知识或策略变化无需使向量失效；同名模型在供应商侧变化时应更新 revision 或等待 TTL。高风险与普通风险不能共用缓存项。

`GET /v1/observability/embedding-cache` 显示 hits/misses/entries/pending，计数按进程、重启清零，不暴露查询内容。不同角色有意不共享该缓存，避免用跨权限复用换取命中率。

## P2：周报试点

流程为 `metrics -> nox -> writing -> 人工审查`。每步输出 `artifact_refs`，不复制完整会话。最后批准只结束草稿流程，不发布、不发送消息。`health` 和 `trades` 不加入这条周报链。

可选依赖与脚本独立于 API 默认镜像：

```bash
python3 -m venv /tmp/mc-orchestration
/tmp/mc-orchestration/bin/pip install -r panopticon/tools/requirements-orchestration.txt
/tmp/mc-orchestration/bin/python -m unittest discover -s panopticon/tools -p 'test_weekly_review_pilot.py'
```

离线 fixture JSON 的格式是三个角色各提供 `{"artifact_refs": ["artifact://..."]}`。路径按本机实际产物指定，不把私密 fixture 提交到仓库。

```bash
/tmp/mc-orchestration/bin/python panopticon/tools/pilot_weekly_review.py \
  --thread-id weekly-demo --checkpoint /tmp/weekly-demo.sqlite \
  --fixtures /path/to/fixtures.json
/tmp/mc-orchestration/bin/python panopticon/tools/pilot_weekly_review.py \
  --thread-id weekly-demo --checkpoint /tmp/weekly-demo.sqlite \
  --fixtures /path/to/fixtures.json --resume approve
```

queue 模式把 `--fixtures` 换成 `--api-url`，从环境读取 `MC_AUTH_TOKEN`，必须传与 worker 配置匹配的 `--provider`。每步预留 20000 token、最多一次尝试。未完成时在 job_wait 检查点暂停；可用 `--resume continue` 手动推进，或用 `--wait` 自动等待作业并推进到人工审查。人工审查只接受 approve/reject，continue 或 wait 不能批准。等待超时保留检查点，不取消已提交作业。

已提供下节所述的无工具草稿 worker，但不调用原生 Gateway Agent、不继承日常会话、渠道或知识工具。SQLite 文件及队列数据库要受访问控制并纳入备份。checkpoint 与队列幂等记录一起保留；删除幂等记录后恢复旧 checkpoint 可能重新提交作业。

## 受控 Worker 接入

[worker 脚本](../panopticon/tools/managed_execution_worker.py) 只消费 metrics/nox/writing 的 main 类别，支持 `workflow=weekly-review`、`mode=draft-only`、对应 step 和 `max_attempts=1`。其他合约被拒绝并标为 FAILED，不执行；当前三角色 main 类别应专用于该 worker，混合其他流程之前需要增加调度能力过滤。

worker 从原配置投影三个角色的 provider、模型、API key 和 AGENTS 说明，直接调用 OpenAI-compatible HTTPS chat completions。API 与模型使用不同 HTTP client，不共享 Authorization，不跟随重定向或环境代理。它没有工具执行接口、Docker socket、生产 workspace/agent-home 挂载或公开端口，不能调用邮件、发布、交易工具。不是把日常 Agent 的完整记忆或知识评估搬到队列中。

三步使用不同 JSON 契约，验证 stage、字段、非空内容及长度，再生成 Markdown：

- metrics：Evidence、Calculations、Missing Data。
- Nox：Priorities、Risks、Decisions for Review。
- writing：Summary、Report、Open Questions。

结构合格不代表事实正确；最终人工审核仍须核对来源、数字与建议。工具调用、空内容、截断输出或不匹配的阶段都会失败，不当作有效草稿。

一次只执行一个作业；API 仍统一控制全局/角色/provider 预算。初次续租成功才执行，之后至多每 10 秒续租；失租、网络续租失败、总期限或 SIGTERM 会取消本地执行，不进行失租后回写。模型 HTTP 超时 120 秒，默认总作业期限 900 秒，自动重放关闭。取消 HTTP 不保证供应商立即停止生成，因此仍可能计费；没有外部工具副作用，也不宣称恰好一次模型执行。

模型输出最多 1024 token，DeepSeek 显式关闭 thinking。序列化请求字节数加输出上限必须不超过作业的申报预留量，否则模型调用前失败。这是保守上界而非 tokenizer 精确估计；20000 预留会限制吞吐。结果中的 usage 记录供应商返回的 token 数，但不会回拨预留预算。

输入只接受 `artifact:<受限文件名>.md`，不会抓取 URL 或读取生产 workspace；路径穿越、符号链接、非普通文件和覆盖已有不同内容被拒绝。每份输入/输出上限 64 KiB，引用总数和队列 JSON 也有界限。API result 只含引用、stage、模式、模型与 usage；失败只记录异常类型/HTTP 状态，不记录原始异常、密钥或正文。

### 启动与配置

[worker overlay](../panopticon/docker-compose.execution-worker.yml) 不修改生成的主 compose。服务为非 root `1000:1000`、只读根文件系统、全部 capability 删除；需要数据目录由 UID 1000 可读写。配置为启动时快照，模型/凭据/角色说明变化后应重新投影并仅重建 worker。

```bash
umask 077
mkdir -p panopticon/mission-control/execution-worker/artifacts
python3 panopticon/tools/managed_execution_worker.py --prepare-roles \
  --state-dir panopticon/mission-control/execution-worker \
  --roles-file panopticon/env/mission-control-worker.json
docker compose -p panopticon \
  -f panopticon/docker-compose.panopticon.yml \
  -f panopticon/docker-compose.lan-https.yml \
  -f panopticon/docker-compose.execution-worker.yml --profile execution \
  up -d --build --no-deps --force-recreate --wait mission-control-execution-worker
```

API 必须已启用队列，且本地 Mission Control env 中 `MC_AUTH_TOKEN` 与 API 一致；不要打印投影文件或环境变量。投影为 600、只读挂载；运行数据目录、凭据投影均被 Git 忽略。健康检查包含最近 API 成功时间，不只是进程存活。后续 compose 运维应包含 worker overlay，避免将其当 orphan 删除；不要用 remove-orphans 清理既有控制器。

### 提交与人工审核

从仓库根目录运行；输入是操作员指定的本地 Markdown。准备命令只输出产物引用，不输出正文：

```bash
THREAD="weekly-$(date +%Y%m%d-%H%M%S)"
REF="$(python3 panopticon/tools/managed_execution_worker.py \
  --state-dir panopticon/mission-control/execution-worker \
  --stage-input /path/to/weekly-input.md)"
docker exec mission-control-execution-worker \
  python -m panopticon.tools.pilot_weekly_review \
  --thread-id "$THREAD" --checkpoint "/data/checkpoints/$THREAD.sqlite" \
  --api-url http://mission-control-api:9090 --provider deepseek \
  --input-ref "$REF" --wait
```

返回三个产物引用和 `pending=human_review`、`approved=false`。在本地运行数据的 artifacts 子目录审阅草稿，再显式结束草稿流程：

```bash
docker exec mission-control-execution-worker \
  python -m panopticon.tools.pilot_weekly_review \
  --thread-id "$THREAD" --checkpoint "/data/checkpoints/$THREAD.sqlite" \
  --api-url http://mission-control-api:9090 --provider deepseek --resume approve
```

拒绝用 `--resume reject`；等待超时后可用 `--resume continue --wait`。失败作业不会自动重做：核对产物/预算/供应商错误后，用新 thread-id 明确重新提交。批准只结束流程，不发送、不发布。不要使用 fixture 模式处理真实队列。

### 停用与恢复

```bash
docker compose -p panopticon \
  -f panopticon/docker-compose.panopticon.yml \
  -f panopticon/docker-compose.lan-https.yml \
  -f panopticon/docker-compose.execution-worker.yml --profile execution \
  stop -t 20 mission-control-execution-worker
```

API 和 8 个 Agent 保持在线。停止时正在执行的作业留待租约到期；API 在后续 claim 中回收，本 worker 的单次作业最终 FAILED，需人工核对。保留队列、产物、checkpoint 与凭据快照，不能通过删除状态来假装成功或重试。

新运行目录和投影需纳入现有备份方案；本轮没有修改定时备份范围或自动清理策略。备份 SQLite 要使用一致性 backup 或停写后完整保存相关文件，不能只复制活跃 WAL 数据库的主文件。恢复时应同时核对 API 数据库和 checkpoint 的幂等记录。原 API 的部署前恢复点不包含本轮 worker 状态。

### 2026-11-14 Worker 验收

- 已上线 `mission-control-execution-worker:weekly-20261114-143920`，镜像 ID `3766fce8df0cee39dc5648628ce346ba89b908a431fbf2ebd76061449b2a2181`，健康且 restart=0；API/UI 及 8 个 Agent 未重建，Agent 启动时间/重启计数未变。
- 实际最终镜像 22 项测试通过，覆盖领取、续租、失租/总期限/关闭取消、权限投影、路径保护、无工具请求、阶段契约、持久化恢复与人工审批。
- 第一轮引用交接成功但三角色内容重复，故补充结构化阶段契约。第二轮合成线程 `worker-acceptance-20261114-143932` 的三个作业均完成，metrics 计算 83.33%/16.67% 并列缺口，Nox 形成待审决策，writing 汇总报告；最终 `human_review`、`approved=false`，没有外部动作。
- 模型配置为 metrics/Nox 的 DeepSeek V4 Flash 和 writing 的 DeepSeek V4 Pro；通过各自模型配置执行，但不是三个 Gateway 日常会话之间的对话。
- 两轮合成草稿和检查点保留用于审阅，不替代真实业务或 8 Agent 负载测量；没有宣称内存收益。原生聊天自动路由、完整知识评估、外部工具 worker、生产 Gateway 合并仍未接入。

## 部署与回滚

上线前保存旧 API 镜像、数据库恢复点、环境变量和可信代理 IP；只重建 API，不重启 8 个 agent。API 重建仍会中断经过它的 WebSocket，需要维护窗口。启动时自动运行 Alembic，新增表是 additive，不修改旧任务列。

先保持队列关闭，验证 `/ready`、任务写入、outbox 和八个聊天代理，再单独启用草稿队列。验证原生渠道、长对话和既有任务后，才能继续接维护脚本或更复杂流程。模板环境变量不会自动覆盖本地 env，也不代表已上线。

回滚 API 镜像时保留新增表，不立即 downgrade。停用队列并等待 RUNNING 作业处理完；确认 outbox pending=0、保存检查点与幂等记录后才考虑退库。降到 `20260524_0013` 会删除本轮队列、outbox 和幂等记录，不应作为默认快速回滚步骤。

## 验收与后续边界

隔离 PostgreSQL 测试覆盖领取竞争、并发预算、幂等冲突、旧租约拒绝、失败次数和 Redis 故障重投；P2 测试覆盖重开检查点、人工拒绝和队列任务重用。测试数据库必须明确为 `mission_control_test`，每项测试使用独立随机 schema。

性能验收须使用相同模型、知识快照和任务，比较单 agent、2-3 agent 和 8 agent 的质量、返工、首 token、总耗时、成本、排队与内存峰值。单元测试的调用次数减少不是生产 CPU 或内存收益。

Gateway 合并、迁移主机、内核 memory cgroup 和原生并发调整未实施。保留全部在线时优先验证低风险角色分组共享运行时，健康/财务角色保持较强边界；需单独授权、试点与同负载测量，不直接推广全体。

## 2026-11-14 实际上线记录

经用户确认，已仅重建 API 并启用托管队列接口；8 个 Agent 启动时间和重启计数未变，模型、渠道、代理信任、UI 与数据库容器均未重建。

- 新镜像：`mission-control-api:p0p1-20261114-135226`，ID `4ea8418572c8ab967abce7a3faf12ef8a6a71710b7e94824342b195a0955f4b4`。
- 回滚镜像：`mission-control-api:rollback-p0p1-20261114-135226`。
- API 原 IP `172.21.0.15` 保持不变，健康且重启计数为 0；数据库迁移到 `20261114_0016`。
- 本地 env 已显式设置 execution/outbox 启用、向量缓存 60 秒和 revision=1。队列预算为 global 4、main 4、subtask 2、maintenance 1、单角色 2。
- 数据库恢复点保留在 gitignored 的 `panopticon/reports/backup-runs/mission-control-before-p0p1-20261114-135226.dump`，118260377 字节、权限 600；不要提交该文件。
- 新镜像内 102 项 API 回归通过，包括一次性 PostgreSQL 并发和故障测试；可选 LangGraph 的 5 项回归通过。新表 migration upgrade/downgrade/upgrade 及模型一致性通过。
- 生产完成一次 noop 队列提交、领取、完成和幂等重放，并写入一条 `execution.acceptance` 审计事件；没有业务执行或模型调用。验收时队列只有 1 个 SUCCEEDED、无过期租约，outbox pending=0，未鉴权访问返回 401。
- 控制台及 8 个 Agent HTTPS 200，8 个 WS 101 与 accept 校验通过。personal 首次 10 秒读取超时，复测约 1.98 秒返回 200，WS 通过、无重启或 OOM；尚未确定首次超时原因，也未验证 8 个模型真实对话。
- 版本、manifest、语法、生成器和 diff 检查通过。既有 skills 模板缺少规定章节，skills gate 未通过；全库 `alembic check` 仍报旧知识模型/索引差异，本轮未修这些无关问题。

快速回滚只恢复镜像，不退数据库；若草稿 worker 已启用，先按 worker 停用步骤停止它，再恢复旧 API：

```bash
docker image tag mission-control-api:rollback-p0p1-20261114-135226 mission-control-api:local
docker compose -p panopticon \
  -f panopticon/docker-compose.panopticon.yml \
  -f panopticon/docker-compose.lan-https.yml \
  up -d --no-deps --no-build --pull never --force-recreate \
  --wait --wait-timeout 180 mission-control-api
```

### 低风险共享 Gateway 基础试点

用户另行允许隔离试点，候选为 `metrics + growth`，模板见 [双角色候选配置](../panopticon/templates/multi-agent-gateway-pilot.json)。OpenClaw 2026.11.3 原生配置校验有效且无警告；临时 Gateway 启动和健康 RPC 通过，报告两个不同的 agentDir/会话路径、会话数均为零。没有生产会话、渠道账号或凭据迁移。

配置显式关闭插件、控制 UI 和跨 agent 工具访问，只有 read 工具。`auth.mode=none` 只允许用于下列无网络、无端口的一次性容器，绝不可直接复制到生产或开放端口：

```bash
docker run --rm --name mc-gateway-isolated-pilot \
  --network none --user node \
  --tmpfs /home/node/.openclaw:rw,uid=1000,gid=1000,size=64m \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -e OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json \
  -e OPENCLAW_STATE_DIR=/home/node/.openclaw \
  -v "$PWD/panopticon/templates/multi-agent-gateway-pilot.json:/home/node/.openclaw/openclaw.json:ro" \
  --entrypoint openclaw openclaw-docker-cn-im:local gateway run
```

最初把配置挂到 `/pilot` 时产生媒体/恢复路径权限错误，已通过正确的临时 state 根目录重测。不要把这类挂载问题当作多 Agent 功能失败，也不要放宽生产目录权限来绕过。

临时 Gateway 和测试数据库/网络均已清理。试点出现过短时事件循环停顿；无账号、无插件、零会话负载不能代表生产稳定性或内存收益。生产合并仍需原生工具边界、角色会话/账号绑定和代表性负载验收；新增无工具草稿 worker 不替代这些验收，也不代表 8 个 Agent 原生聊天已自动使用队列。

## 2026-11-14 只读知识与 Nox 显式路由迭代

本轮已上线 API 角色知识访问、worker 只读知识评估和 Nox 显式三角色周报路由。没有全量接管原生聊天、Feishu、cron 或其他渠道，也没有迁移生产会话、合并 Gateway、调整原模型或重启八个 Agent。

### 已启用的边界

- 八个角色的 `knowledge-eval` 原生 YAML 元数据已修复，客户端与标准包装器同步；以 `openclaw skills list --json` 的 eligible 判断发现状态。growth 已有多个 owner，检查时需 `--agent growth`，不能回滚其配置。
- 每角色使用私有 `agent-homes/<role>/knowledge-access.json`。API 从 `env/knowledge-access.json` 只加载 token 的 SHA256 与角色/风险下限；角色 token 只允许 resolve，不允许队列或知识管理。health/trades 下限 high，其他角色 normal；强制最新 approved、未过期、最多 5 项，并返回可关联的 audit_id。
- 这只隔离了新增知识凭据，**没有撤销原生 Agent 历史环境中的管理 token**。不得描述为整个控制面已经完成最小权限隔离。
- worker 默认 lexical，只转发公开或同时授权 metrics/nox/writing 的知识摘要；最多两项、每项 512 字符，记录完整内容 SHA256。阶段交接和生成后交付都复核；无法再次确认原版本/授权时停止。候选掉出 top-5 也可能保守停止，不等同于已经证明知识撤销。
- normal 无知识时仍只产草稿，附确定的 Evidence Check/no_hit；high/critical 没有可纳入证据时拒绝模型调用。知识不可信文本不能扩展工具权限。
- 申报预算仍为每阶段 20,000。按序列化请求字节加最大输出作保守上界；完整输入和强制安全/输出契约不截短，只按剩余空间截短辅助 AGENTS 说明，并记录 `role_guidance_truncated`。过大的输入仍会拒绝，不保证所有 8 KiB 输入都能与上下游草稿一起装入。
- worker 只领取 weekly-review 能力。取消 QUEUED/RUNNING 后旧租约 heartbeat/finish 返回 409；关闭期间不继续提交下一阶段。失败模型任务不自动重试。

### 以后如何对话

在 Nox 中提供稳定编号和明确共享确认，例如：

> 任务编号 weekly-2026w46。请让 metrics 分析以下数据、Nox 汇总决策、writing 写周报草稿。我允许这份输入在三个角色之间共享；只生成草稿，停在人工审核，不发布。

普通聊天不走此路由；没有稳定编号或共享确认时先补充，不自动拷贝会话历史、个人记忆或其他角色私有文件。重试必须复用相同编号和相同输入，异内容返回 409。高风险医疗、交易、邮件发送和发布不属于本路由。

`weekly-review-route` 只安装在 Nox。内部 HTTP 9190 不发布到主机，专用凭据仅支持 submit/status/cancel，没有 approve/reject。最多两条活跃流程，每分钟最多五次新提交。`origin_session` 和共享确认只是可信调用方声明，不是原生签名；只有相同稳定 ID 才去重，不保证所有原生重连天然去重。

原生 CLI 可查询状态，不应循环轮询：

```bash
docker exec openclaw-nox python3 \
  /home/node/.openclaw/workspace/skills/weekly-review-route/scripts/weekly_route.py \
  status --request-id weekly-2026w46
```

REVIEW 不是批准。操作者检查私有产物后，沿前文 pilot CLI 使用对应 thread_id/checkpoint 明确 approve/reject；这只记录审核决定，不发送或发布。取消后不复用旧检查点推进，应新建明确授权的任务。无自动完成通知或新增 UI 按钮。

### 安装与恢复

运行时 workspaces/agent-homes 被 Git 忽略；只更新 global skill 不会同步原生副本。先对照标准版本检查定制差异，再同步 `global-skills/knowledge-eval/scripts/` 的客户端/包装器到八角色，并把 `global-skills/weekly-review-route/` 同步到 Nox；保留各角色 SKILL 正文，不覆盖用户定制文件。

```bash
python3 panopticon/tools/managed_execution_worker.py --prepare-knowledge-access \
  --knowledge-access-file panopticon/env/knowledge-access.json
python3 panopticon/tools/managed_execution_worker.py --prepare-roles \
  --roles-file panopticon/env/mission-control-worker.json
```

已有凭据重复准备不轮换。手工轮换须协调角色文件、API 摘要 profile、worker 投影并重建相应服务；准备工具不会自动清理旧摘要，必须显式撤销旧 profile。不得打印或提交明文配置。最后用主 compose、LAN HTTPS overlay、execution overlay 三层配置重建 API/worker；不能遗漏 HTTPS 与代理信任配置。

本轮 API `mission-control-api:knowledge-20261114-154855`，worker `mission-control-execution-worker:knowledge-20261114-154855-budgetfix`。API 保持 `172.21.0.15`。回滚镜像分别为 `mission-control-api:rollback-knowledge-20261114-154855` 和 `mission-control-execution-worker:rollback-knowledge-20261114-154855`。

停用路由/自动知识可将 worker overlay 中对应 enabled 值设为 `"0"` 并仅重建 worker；仍保留角色凭据与审核状态。完全暂停则停止 worker。回滚旧 API 前先停 worker，保留新角色凭据使不支持它们的旧 API 拒绝知识访问，不自动回退到管理凭据或放宽认证。不要自动降级数据库。

私有恢复点位于 gitignored `panopticon/reports/backup-runs/`：`before-knowledge-20261114-154855.dump` 与同前缀 `-worker-private.tar.gz`，均 600。worker 停止后保存检查点、路由库、产物、八角色凭据和投影；另保留首次失败后的状态包。备份含密钥，需要受控存储，权限 600 不等于加密。

### 验收结果与限制

实际镜像 API 107 项（含一次性 PostgreSQL）、worker/路由 32 项通过；客户端/元数据 10 项与备份 14 项通过。八角色线上风险下限、跨角色 403、管理接口 403 与 audit_id 通过；控制台 HTTPS 200。无知识高风险在模型调用前被拒绝，RUNNING 取消的旧 heartbeat/finish 均 409。

首次合成流程 writing 因完整辅助说明导致字节预算不足而 FAILED，没有模型调用或自动重试；该记录保留。修复后独立请求 `weekly-acceptance-20261114-160118` 完成三阶段，停在 REVIEW，approved=false。合成查询均 no_hit；实际证据命中/撤销/私有 scope 的正确性由隔离测试验证，未向生产知识库写入测试资料。

原生 skills 可发现且 Nox 容器凭据路由通过，不等于已验证真实用户对话中模型必然选择此 skill。尚未测八角色代表性负载、长期稳定性、真实知识质量或内存节省。全量原生准入仍需渠道/会话签名、流式协议、取消、模型/子代理预算与工具白名单验收。既有 PPT/AutoML 等 skill 章节 gate 仍失败，本轮未修改无关 skill。