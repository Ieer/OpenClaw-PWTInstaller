# 8-Agent Personal Panopticon

这份文档服务于仓库的当前主路线：`8-Agent Panopticon + Mission Control`。

如果你的目标只是先把 OpenClaw 跑起来，先看 [../README.md](../README.md) 的单 Agent 路线；如果你要长期运行多角色 Agent、统一观察状态、接入知识系统和控制台，本页就是起点。

## 这一套东西包含什么

- 8 个隔离的 OpenClaw agent：`nox / metrics / email / growth / trades / health / writing / personal`
- Mission Control UI：统一入口、状态面板、feed、嵌入式聊天
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

### 2. 复制本地 env 覆盖文件

```bash
for example in panopticon/env/*.env.example; do
  target="${example%.example}"
  if [ ! -f "$target" ]; then
    cp "$example" "$target"
  fi
done
```

说明：公开仓库提交的是 `*.env.example`，Compose 实际读取的是本地 `*.env`。

### 3. 轮换 Gateway token

当 `agent_runtime.gateway_auth_mode=token` 时，这是启动前必做项：

```bash
bash panopticon/tools/rotate_gateway_tokens.sh
```

`validate_panopticon.py` 会拒绝 `CHANGE_ME_*`、`TODO`、`REPLACE_ME` 一类占位值。

### 4. 编辑必要配置

最少需要改这些文件：

- [agents.manifest.yaml](agents.manifest.yaml)
- [env/mission-control.env.example](env/mission-control.env.example) 复制出的本地 `mission-control.env`
- [env/mission-control-ui.env.example](env/mission-control-ui.env.example) 复制出的本地 `mission-control-ui.env`
- [env/mission-control-gateway.env.example](env/mission-control-gateway.env.example) 复制出的本地 `mission-control-gateway.env`
- [env/nox.env.example](env/nox.env.example) 复制出的本地 `nox.env`
- [env/metrics.env.example](env/metrics.env.example) 复制出的本地 `metrics.env`
- [env/email.env.example](env/email.env.example) 复制出的本地 `email.env`

通常至少要填写：

- 模型 ID、Base URL、API Key
- `OPENCLAW_GATEWAY_TOKEN`
- Mission Control 所需的数据库、鉴权和知识系统相关变量

按需启用的附加文件：

- 远程容器控制：编辑本地 `mission-control.env`，来源见 [env/mission-control.env.example](env/mission-control.env.example)
- 语音桥接：编辑本地 `mission-control-voice-bridge.env`，来源见 [env/mission-control-voice-bridge.env.example](env/mission-control-voice-bridge.env.example)

### 5. 可选：指定数据目录

推荐把运行态数据移出 Git 工作树，在 [../panopticon/.env.example](../panopticon/.env.example) 的本地副本里设置：

- `PANOPTICON_DATA_DIR`
- `PANOPTICON_USB_HOST_PATH`
- `PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH`

如果以上变量都不设置，最小启动会使用仓库内默认目录，例如 `./mission-control/knowledge-sources`。

### 6. 生成并校验

```bash
python panopticon/tools/generate_panopticon.py --prune
python panopticon/tools/validate_panopticon.py
python panopticon/tools/validate_skills_template.py
docker compose -f panopticon/docker-compose.panopticon.yml config >/tmp/panopticon.compose.rendered.yml
```

### 7. 启动

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d
```

如需语音桥接：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml --profile voice up -d mission-control-voice-bridge
```

### 8. 验收入口

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
docker compose -f panopticon/docker-compose.panopticon.yml ps
docker compose -f panopticon/docker-compose.panopticon.yml logs -f --tail=200
bash panopticon/tools/check_panopticon_services.sh
```

如果 UI 或网关出现 502，优先执行：

```bash
bash panopticon/tools/recover_mission_control_gateway.sh
```

## 常见约束

- 统一从 `18920` 的同源入口访问 chat，不要直接打开 `188xx` 端口。
- schema 变更统一走 Alembic，不再依赖容器启动期补建表。
- `mission-control-agent-controller` 属于高风险能力，只在确实需要远程启停容器时再开启。
- 本地 `.env` 和运行态数据都不应进入 Git。

## 深入阅读

如果你已经跑通最小启动，再根据目标深入：

- 开机自启与巡检：查看下方“开机自启”章节。
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

说明：该巡检已集成 voice-bridge E2E（统一入口）。

- 默认 `CHECK_VOICE_E2E=auto`：仅当 `mission-control-voice-bridge` 运行时才执行 E2E。
- `CHECK_VOICE_E2E=1`：强制执行 voice E2E（容器未运行将直接失败）。
- `CHECK_VOICE_E2E=0`：跳过 voice E2E，仅检查服务运行状态。

示例：

```bash
CHECK_VOICE_E2E=1 bash panopticon/tools/check_panopticon_services.sh
```

一键巡检 8 个 Agent 端点（Gateway 按 HTTP、Bridge 按 TCP）：

```bash
bash panopticon/tools/check_agent_endpoints.sh
```

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
