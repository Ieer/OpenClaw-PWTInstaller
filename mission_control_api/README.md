# Mission Control API

Mission Control API 是 Panopticon 主路线的后端中枢，负责把多 Agent、控制台、知识系统和事件流接到同一个运行面上。

如果你只是想把系统跑起来，先看 [../panopticon/README.md](../panopticon/README.md)。
如果你要改 API、数据模型或知识链路，再读本页。

## 服务职责

当前后端已提供：

- REST：健康检查、任务板、评论、活动流、skills mapping、usage 聚合。
- Chat 代理：同源 HTTP / WebSocket 代理到各个 agent。
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
- skills mapping
- usage 聚合
- agent catalog
- chat 代理

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

## 回归与验收

仓库已经提供面向知识系统和主路线的专项脚本，提交前优先跑与你改动相关的那组：

- [../tools/verify_knowledge_p0_regression.sh](../tools/verify_knowledge_p0_regression.sh)
- [../tools/verify_knowledge_ocr_flow.sh](../tools/verify_knowledge_ocr_flow.sh)
- [../tools/verify_knowledge_dynamic_policy_rollout_flow.sh](../tools/verify_knowledge_dynamic_policy_rollout_flow.sh)
- [../tools/verify_knowledge_policy_governance_flow.sh](../tools/verify_knowledge_policy_governance_flow.sh)
- [../tools/benchmark_knowledge_hybrid_resolve.sh](../tools/benchmark_knowledge_hybrid_resolve.sh)

## 延伸阅读

- 主路线启动与运维：[../panopticon/README.md](../panopticon/README.md)
- 工程落地手册：[../docs/mission-control-playbook-zh-cn.md](../docs/mission-control-playbook-zh-cn.md)
- 知识系统手册：[../docs/knowledge-system-playbook-zh-cn.md](../docs/knowledge-system-playbook-zh-cn.md)
