# Mission Control API

Mission Control API 是 Panopticon 主路线的后端中枢，负责把多 Agent、控制台、知识系统和事件流接到同一个运行面上。

如果你只是想把系统跑起来，先看 [../panopticon/README.md](../panopticon/README.md)。
如果你要改 API、数据模型或知识链路，再读本页。

## 服务职责

当前后端已提供：

- REST：健康检查、任务板、评论、活动流、skills mapping、usage 聚合。
- Chat 代理：同源 HTTP / WebSocket 代理到各个 agent。
- Voice command adapter：可选把 `voice.asr.final` 中的显式命令语法翻译成任务创建、评论、状态流转、handoff 与 agent 控制事件。
- Knowledge API：source、chunk、OCR、validation、resolve、feedback、lifecycle。
- 实时事件：通过 Redis Streams 向 Mission Control UI 提供事件流。
- 数据存储：Postgres 为主，Redis 为实时流与缓存。

## 开发前先知道

- 主路线是 `8-Agent Panopticon + Mission Control`。
- schema 变更统一通过 Alembic 管理，不再依赖运行时 DDL 兜底。
- 本服务已经被 [../panopticon/docker-compose.panopticon.yml](../panopticon/docker-compose.panopticon.yml) 集成，不建议脱离主路线假设来写代码。

## 本地开发最短路径

```bash
cd mission_control_api
python -m pip install -r requirements.txt
alembic upgrade head
```

如果你从仓库根目录联调整套系统，常用命令是：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d mc-postgres mc-redis mission-control-api
curl -fsS http://127.0.0.1:18910/health
```

## Chat 代理与设备认证

- OpenClaw 2026.11.3 要求可信代理提供真实客户端来源。nginx 的 `/chat/` 路由覆盖 `X-Forwarded-For`，API 不再伪装回环地址。
- 在本地 Mission Control 环境文件中设置 `MC_CHAT_TRUSTED_PROXY_IPS`，逗号分隔，仅填写直接连接 API 的 nginx 实际 IP；默认空值不信任任何转发头。不要填写整个 Docker 子网。
- 各 agent 的 `gateway.trustedProxies` 仅信任直接连接它的 API 实际 IP。重建代理容器或 Docker 网络后应核对并同步这两层地址。
- 浏览器通过 HTTPS 或 localhost 安全上下文生成设备身份，并使用正常配对流程。`MC_CHAT_COMPAT_CLEAR_DEVICE_AUTH_STORAGE`、`MC_CHAT_COMPAT_STRIP_STALE_DEVICE_FIELDS` 和 `MC_CHAT_COMPAT_FORCE_TOKEN_IN_CONNECT` 默认关闭，避免破坏签名及已配对凭据。
- `MC_CHAT_PROXY_FORCE_LOOPBACK_HEADERS` 已不再控制代理来源，不应依靠旧版回环伪装或退休的设备认证绕过配置。

## 你最常改的地方

| 路径 | 作用 |
| --- | --- |
| [app/main.py](app/main.py) | FastAPI 入口与路由装配 |
| [app/models.py](app/models.py) | SQLAlchemy 数据模型 |
| [app/schemas.py](app/schemas.py) | Pydantic schema |
| [app/agent_catalog.py](app/agent_catalog.py) | Agent catalog 与主路线集成 |
| [alembic/versions/](alembic/versions/) | schema 迁移脚本 |

## API 范围

### 控制面 API

- 健康检查
- board / feed / tasks / comments
- voice-driven task / handoff / status / comment orchestration（通过 `/v1/events` 写入 `voice.asr.final`）
- skills mapping
- usage 聚合
- agent catalog
- chat 代理

### 用量读取与缓存

`GET /v1/usage/agents?days=7` 使用进程内快照，完成重建后默认缓存 60 秒，可通过 `MC_AGENT_USAGE_CACHE_TTL_SECONDS` 调整（最小 1 秒，恢复原频率可设为 15）。过期快照立即返回，后台只允许一轮日志扫描；冷启动等待受 `agent_usage_snapshot_timeout_seconds` 限制，超时返回空列表，后台扫描继续。扫描失败保留旧快照，因此该接口不提供强实时一致性，多 worker 的缓存也不共享。

未变化的日志复用解析结果，文件指纹包含设备、inode、大小、纳秒修改时间及状态变更时间。追加、改写和轮转会重新解析，删除会清理缓存；24 小时和指定天数窗口每轮重新计算。解析缓存最多保留 16384 个文件、50000 条用量记录，只保存用量数据，不缓存会话正文。超出预算的文件仍正常读取，但不进入缓存。

相关回归位于 [tests/test_health_endpoints.py](tests/test_health_endpoints.py)，涵盖后台单次刷新、冷启动超时、文件变更和滑动窗口。

### 知识系统 API

- sources：导入与扫描原始资料
- chunk：把资料切成 knowledge units
- OCR：图片和扫描 PDF fallback
- validations：记录验证状态与过期信息
- policy：risk policy、bundle、rule、rollout
- resolve：lexical / semantic / hybrid 召回与审计
- feedback / lifecycle：回流事件和知识单元状态迁移

## 数据迁移规则

必须遵守的约束：

- 所有 schema 变更都要提交 Alembic 迁移。
- 迁移脚本必须可重复执行，并包含 downgrade。
- 不要在 [app/main.py](app/main.py) 里恢复启动期建表逻辑。
- 生产迁移遵循“先兼容、再切流、最后清理”的 expand/contract 策略。

常用命令：

```bash
alembic upgrade head
alembic revision -m "your migration message"
alembic downgrade -1
```

容器启动时，[docker-entrypoint.sh](docker-entrypoint.sh) 会先执行 `alembic upgrade head`，成功后再启动 Uvicorn。迁移失败会被标记为 `db-not-ready`、`db-auth`、`db-host`、`migration-error` 或 `unknown`：连接未就绪和 DNS 类问题会继续按 `MC_DB_MIGRATION_MAX_RETRIES` 重试，认证失败和迁移脚本错误会快速退出，避免把确定性配置错误伪装成长时间等待。

提交前可以用下面的命令同时检查 entrypoint 语法和分类规则：

```bash
sh -n mission_control_api/docker-entrypoint.sh
python -m unittest discover -s mission_control_api/tests -p 'test_docker_entrypoint.py'
```

## 回归与验收

仓库已经提供面向知识系统和主路线的专项脚本，提交前优先跑与你改动相关的那组：

- [../tools/verify_knowledge_p0_regression.sh](../tools/verify_knowledge_p0_regression.sh)
- [../tools/verify_knowledge_ocr_flow.sh](../tools/verify_knowledge_ocr_flow.sh)
- [../tools/verify_knowledge_dynamic_policy_rollout_flow.sh](../tools/verify_knowledge_dynamic_policy_rollout_flow.sh)
- [../tools/verify_knowledge_policy_governance_flow.sh](../tools/verify_knowledge_policy_governance_flow.sh)
- [../tools/benchmark_knowledge_hybrid_resolve.sh](../tools/benchmark_knowledge_hybrid_resolve.sh)

## 延伸阅读

- 主路线启动与运维：[../panopticon/README.md](../panopticon/README.md)
- 真实语音设备联调：[../docs/voice-device-bringup-zh-cn.md](../docs/voice-device-bringup-zh-cn.md)
- 工程落地手册：[../docs/mission-control-playbook-zh-cn.md](../docs/mission-control-playbook-zh-cn.md)
- 知识系统手册：[../docs/knowledge-system-playbook-zh-cn.md](../docs/knowledge-system-playbook-zh-cn.md)
