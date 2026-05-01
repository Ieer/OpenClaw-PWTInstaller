# 8-Agent Personal Panopticon

这份文档服务于仓库的当前主路线：`8-Agent Panopticon + Mission Control`。

如果你的目标只是先把 OpenClaw 跑起来，先看 [../README.md](../README.md) 的单 Agent 路线；如果你要长期运行多角色 Agent、统一观察状态、接入知识系统和控制台，本页就是起点。

## 这一套东西包含什么

- 8 个隔离的 OpenClaw agent：`nox / metrics / email / growth / trades / health / writing / personal`
- Mission Control UI：统一入口、状态面板、feed、嵌入式聊天。Agents 状态只分两档：`RECENT` 表示最近 30 分钟内有活动，`IDLE` 表示更久未见活动；状态色体现在头像上，不再单独占用右侧状态块。
- Mission Control API：事件、任务、chat 代理、knowledge API
- Mission Control Gateway：同源入口，统一承载 `/` 与 `/chat/<agent>/`
- manifest、env 模板、生成器、校验器和运维脚本

当前定位：

- 主推路线：Panopticon + Mission Control
- 次要路线：单 Agent 命令行安装器
- 实验性路线：仓库根目录单容器 Docker

## 先决条件

| 项目 | 建议 |
| --- | --- |
| Docker / Docker Compose | 必需 |
| Python | 3.11+ |
| Node.js | 22+ |
| 可写数据目录 | 推荐独立磁盘或外接 SSD |

## 10 分钟启动

### 1. 安装工具依赖

```bash
python -m pip install -r panopticon/tools/requirements.txt
```

### 2. 先确认要填哪些配置

首次运行 bootstrap 脚本会自动从 `*.env.example` 复制缺失的本地覆盖文件，但不会替你填写真实值。请先确认这些本地文件里的关键项：

- [env/mission-control.env](env/mission-control.env)
- [env/mission-control-ui.env](env/mission-control-ui.env)
- [env/mission-control-gateway.env](env/mission-control-gateway.env)
- [env/nox.env](env/nox.env)
- [env/metrics.env](env/metrics.env)
- [env/email.env](env/email.env)
- [env/growth.env](env/growth.env)
- [env/trades.env](env/trades.env)
- [env/health.env](env/health.env)
- [env/writing.env](env/writing.env)
- [env/personal.env](env/personal.env)
- [.env](.env)（可选，用于自定义 `PANOPTICON_DATA_DIR`）

通常至少要填写：

- 模型 ID、Base URL、API Key
- `OPENCLAW_GATEWAY_TOKEN`
- Mission Control 所需的数据库、鉴权和知识系统相关变量

按需启用的附加文件：

- 远程容器控制：默认关闭；如需启用，先在本地把 `agents.manifest.yaml` 中的 `mission_control.agent_controller_enabled` 改为 `true`，再编辑本地 `mission-control.env`，来源见 [env/mission-control.env.example](env/mission-control.env.example)
- 语音桥接：编辑本地 `mission-control-voice-bridge.env`，来源见 [env/mission-control-voice-bridge.env.example](env/mission-control-voice-bridge.env.example)

### 3. 一键 bootstrap / 轮换 token

```bash
bash panopticon/tools/rotate_gateway_tokens.sh
```

说明：脚本会自动补齐缺失的 `panopticon/.env` 和 `panopticon/env/*.env` 本地覆盖，轮换 token，生成 Compose，校验 manifest / release / skills，并重启相关服务。

### 4. 启动后先做什么

```bash
bash panopticon/tools/check_panopticon_services.sh
```

如果你还想做系统级巡检，也可以跑 [../tools/check_services_health.sh](../tools/check_services_health.sh)。

如需语音桥接：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml --profile voice up -d mission-control-voice-bridge
```

如果你准备联调真实语音设备，优先看 [../docs/voice-device-bringup-zh-cn.md](../docs/voice-device-bringup-zh-cn.md)。

如果你想先做一轮更完整的语音评估，再看 [../docs/voice-device-bringup-zh-cn.md](../docs/voice-device-bringup-zh-cn.md) 里的分层评估脚本 `python panopticon/tools/assess_voice_service.py`。

### 5. 验收入口

- Mission Control UI：<http://127.0.0.1:18920/>
- 同源 Chat：<http://127.0.0.1:18920/chat/nox/>
- API 健康检查：<http://127.0.0.1:18910/health>

## 运行结构

最重要的分层只有五层：

1. `agents.manifest.yaml`：单一来源，定义 agent、端口和生成规则。
2. `docker-compose.panopticon.yml`：生成后的运行编排，不建议长期手改。
3. `env/*.env`：每个 agent 和 Mission Control 的本地配置。
4. `PANOPTICON_DATA_DIR`：持久化目录，承载 workspaces、agent homes、Postgres、Redis。
5. `tools/`：生成、校验、巡检、恢复和专项验收脚本。

一句话记忆：改名单看 manifest，改密钥看 env，改数据位置看 `.env`。

## 启动后先做什么

```bash
bash panopticon/tools/check_panopticon_services.sh
```

如果你还想做系统级巡检，再跑 [../tools/check_services_health.sh](../tools/check_services_health.sh)。

如果 UI 或网关出现 502，优先执行：

```bash
bash panopticon/tools/recover_mission_control_gateway.sh
```

## 备份、迁移与保留

Panopticon 主路线的数据不等于单一 `~/.openclaw` 目录；迁移级备份需要同时覆盖 agent homes、workspaces、Mission Control PostgreSQL、env 覆盖文件、知识源和运行指纹。策略说明见 [../docs/openclaw-backup-retention-zh-cn.md](../docs/openclaw-backup-retention-zh-cn.md)。

先查看当前备份边界：

```bash
python panopticon/tools/backup_panopticon.py plan
```

日常不停机增量备份推荐走 restic + PostgreSQL 逻辑 dump：

```bash
export RESTIC_PASSWORD='replace-with-a-strong-password'
python panopticon/tools/backup_panopticon.py \
	--backup-root /media/pi/YOUR_USB/openclaw-backups \
	daily-incremental \
	--init-restic \
	--restic-check
```

迁移级或升级前全量冷备需要低峰期短暂停服务：

```bash
python panopticon/tools/backup_panopticon.py \
	--backup-root /media/pi/YOUR_USB/openclaw-backups \
	weekly-full \
	--yes \
	--restart-after
```

每次 OpenClaw 大版本升级、Mission Control schema 变更或容器挂载重构前，都应先生成并校验一份 full baseline。

## 升级与回滚

主路线的运行态替换现在统一走仓库根目录 `tools/` 里的发布脚本，不再建议手工拼接 `docker compose build` 和 `up --force-recreate`。

常用快路径：

```bash
python tools/prepare_release_upgrade.py --level light --skip-smoke
python tools/rollout_release_upgrade.py --mode fast-panopticon
bash panopticon/tools/check_agent_endpoints.sh
```

需要回退时：

```bash
python tools/rollback_release_upgrade.py
```

- `fast-panopticon` 适合只刷新 OpenClaw agent 容器，默认走轻量 prepare 和 agent endpoint 校验。
- `release` 模式适合完整发布链路，默认会带上 Mission Control，并走更重的 smoke 校验。
- rollout 和 rollback 都带运行版本门禁；如果目标服务版本完全没变化，脚本会直接失败，而不是把 no-op 当成功。
- 最近一次升级的 metadata 会写到 `.release-state/last-rollout.json`；更完整的参数、模式与字段说明见 [../docs/openclaw-cli-cheatsheet-zh-cn.md](../docs/openclaw-cli-cheatsheet-zh-cn.md)。

### OpenClaw 2026.4.24 飞书升级修复

如果升级到 `2026.4.24` 后，某个 agent 的飞书渠道开始持续重启，并在日志里看到下面任一报错：

- `Cannot find package 'openclaw' imported from .../plugin-runtime-deps/.../dist/extensions/feishu/monitor-*.js`
- `failed to load bundled channel setup feishu: Cannot find module '@larksuiteoapi/node-sdk'`

优先判断为 stock:feishu 运行时依赖解析问题，而不是飞书凭证或事件订阅配置错误。

当前仓库已经内置修复：

- 启动时自动把 `plugin-runtime-deps/node_modules/openclaw` 桥接到全局 `openclaw` 包。
- 构建镜像时为 stock Feishu 扩展补装它自己的生产依赖。

修复生效方式不是只重启 gateway，而是重建目标 agent 容器。例如：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build --no-deps openclaw-nox
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build --no-deps openclaw-email openclaw-growth openclaw-health openclaw-metrics openclaw-personal openclaw-trades openclaw-writing
```

如果只想局部验证，也可以只重建一个或几个 `openclaw-*` 服务。更完整的排障说明见 [../docs/feishu-setup-zh-cn.md](../docs/feishu-setup-zh-cn.md)。

### OpenClaw 2026.4.29 飞书 open 策略修复

`2026.4.29` 起，飞书 `dmPolicy="open"` 需要显式声明 `allowFrom=["*"]`。否则日志里可能出现：

```text
blocked unauthorized sender ... (dmPolicy=open)
```

当前仓库的 agent 镜像启动脚本会在合并配置时自动补齐该字段；如果是升级前遗留配置，建议重建并重启目标 agent 容器。

单 agent 示例：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml build openclaw-nox
docker compose -f panopticon/docker-compose.panopticon.yml up -d --no-deps --force-recreate openclaw-nox
```

8-Agent 全量刷新后，建议至少执行：

```bash
bash panopticon/tools/check_agent_endpoints.sh
bash panopticon/tools/check_panopticon_services.sh
```

飞书发送链路可用性的最终判定，是使用当前 `channels.feishu.appId/appSecret` 获取 `tenant_access_token` 成功，并调用飞书 `im/v1/messages` 返回 `code=0`。

## 常见约束

- 统一从 `18920` 的同源入口访问 chat，不要直接打开 `188xx` 端口。
- schema 变更统一走 Alembic，不再依赖容器启动期补建表。
- `mission-control-agent-controller` 属于高风险能力，只在确实需要远程启停容器时再开启。
- 本地 `.env` 和运行态数据都不应进入 Git。

## 深入阅读

如果你已经跑通最小启动，再根据目标深入：

- 开机自启与巡检：查看下方“开机自启”章节。
- 升级与回滚：查看上方“升级与回滚”，需要完整参数说明时再看 [../docs/openclaw-cli-cheatsheet-zh-cn.md](../docs/openclaw-cli-cheatsheet-zh-cn.md)。
- UI / Gateway 故障：查看下方“运维重启顺序”和“Control UI 推荐入口与 1008 排障”。
- Agent 增删：查看下方“增删 Agent 快速作业”。
- Mission Control 的工程解释：看 [../docs/mission-control-playbook-zh-cn.md](../docs/mission-control-playbook-zh-cn.md)。
- 知识系统治理：看 [../docs/knowledge-system-playbook-zh-cn.md](../docs/knowledge-system-playbook-zh-cn.md)。

---

## 开机自启（Mission Control 一条命令）

启用（创建并启动 systemd 服务）：

```bash
bash panopticon/tools/setup_mission_control_autostart.sh
```

启用并包含语音桥接 profile（开机自动拉起 `mission-control-voice-bridge`）：

```bash
bash panopticon/tools/setup_mission_control_autostart.sh --with-voice
```

停用（移除 systemd 服务）：

```bash
bash panopticon/tools/setup_mission_control_autostart.sh --disable
```

该服务统一管理 `mc-redis`、`mc-postgres`、`mission-control-api`、`mission-control-ui`、`mc-heartbeat` 以及 8 个 `openclaw-*` agent 容器。

一键巡检 13 个服务（红绿结果）：

```bash
bash panopticon/tools/check_panopticon_services.sh
```

说明：该巡检已集成 voice assessment smoke（统一入口）；完整 command closure 请单独跑 `python panopticon/tools/assess_voice_service.py`。

- 默认 `CHECK_VOICE_E2E=auto`：仅当 `mission-control-voice-bridge` 运行时才执行 voice assessment smoke。
- `CHECK_VOICE_E2E=1`：强制执行 voice assessment smoke（容器未运行将直接失败）。
- `CHECK_VOICE_E2E=0`：跳过 voice assessment smoke，仅检查服务运行状态。

示例：

```bash
CHECK_VOICE_E2E=1 bash panopticon/tools/check_panopticon_services.sh
```

联调真实设备时，建议再跑一遍 live 检查：

```bash
bash panopticon/tools/check_voice_bridge_live.sh
```

如果你要的是“整体语音服务是否可用”，先跑：

```bash
python panopticon/tools/assess_voice_service.py
```

一键巡检 8 个 Agent 端点（Gateway 按 HTTP、Bridge 按 TCP）：

```bash
bash panopticon/tools/check_agent_endpoints.sh
```

一键巡检 8 个 Agent 的 Python 运行态（`python3`、`pip`、`PyYAML`）：

```bash
bash panopticon/tools/check_agent_python_runtime.sh
```

当前 `openclaw-docker-cn-im:local` 基线已在镜像内预装 `python3-pip`、`python3-venv`、`python3-yaml`。这对 self-heal、YAML registry、脚本化治理和 agent 内部 Python 辅助工具是必需项。若该脚本失败，应优先重建共享 agent 镜像并 force-recreate 目标 `openclaw-*` 容器。

## 运维重启顺序（避免 502）

当你重建或重启 `mission-control-ui` 后，建议按以下顺序操作：

优先直接执行一键恢复脚本：

```bash
bash panopticon/tools/recover_mission_control_gateway.sh
```

该脚本会自动完成：重建 `mission-control-api` / `mission-control-ui`、强制重建 `mission-control-gateway`，并校验 `18920` 首页与 `18910/health`。

如果你需要手工执行，再按以下顺序操作：

1. 重建或重启 API 与 UI：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build mission-control-api mission-control-ui
```

2. 强制重建 Gateway：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --force-recreate mission-control-gateway
```

3. 快速验收：

```bash
curl -I http://localhost:18920/
curl -fsS http://127.0.0.1:18910/health
```

## Control UI（Web Chat）推荐入口与 1008 排障

推荐入口：

```text
http://127.0.0.1:18920/chat/<agent>/
```

不要直接打开 `188xx` host 端口。那样最容易出现：

- `token missing`
- `disconnected (1008)`
- `pairing required`

主路线下这些问题通常来自三类原因：

1. Gateway token 不一致。
2. 绕过了同源网关。
3. 配对状态或 trusted proxies 配置不一致。

优先修复动作：

```bash
bash panopticon/tools/rotate_gateway_tokens.sh
docker compose -f panopticon/docker-compose.panopticon.yml up -d --force-recreate mission-control-gateway
```

## 增删 Agent 快速作业

最小原则：优先改 [agents.manifest.yaml](agents.manifest.yaml)，再重新生成，不要长期手改 compose。

标准流程：

```bash
python panopticon/tools/generate_panopticon.py --prune
python panopticon/tools/validate_panopticon.py
docker compose -f panopticon/docker-compose.panopticon.yml up -d
```

## 端口映射（host → container）

- `18920` → Mission Control Gateway / UI 统一入口
- `18910` → Mission Control API
- `188xx` → 各 agent 的 OpenClaw gateway host port
- `1879x` / `1887x` 类端口 → 各 agent bridge host port

## Mission Control Chat（内嵌对话）

Mission Control UI 通过同源 `/chat/<agent>/` 入口嵌入各 agent 的对话界面。推荐只保留同源入口，不对新用户暴露直连地址。

## 数据隔离

每个 agent 都拥有独立的 home 与 workspace；Mission Control 的数据库、Redis 和日志与 agent 运行态数据分层存放。建议把运行态数据与 Git 工作树分离。

## 注意事项

- 不要把 `18920` 暴露到不可信网络。
- 不要提交 `.env`、token、数据库备份和运行态产物。
- 容器控制器、语音桥接等能力都应按需启用，而不是默认全开。
