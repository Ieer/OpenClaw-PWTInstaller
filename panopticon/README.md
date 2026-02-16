# 8-Agent Personal Panopticon（Docker Compose）

这是一份 **8-service** 的 Docker Compose 模板，用于启动 8 个隔离的 OpenClaw agent（nox/metrics/email/growth/trades/health/writing/personal），并对齐 CN-IM 镜像的 **env → openclaw.json** 生成方式。

入口文件：

- Compose： [panopticon/docker-compose.panopticon.yml](panopticon/docker-compose.panopticon.yml)
- 每 agent env_file： [panopticon/env/](panopticon/env/)
- Agent 清单（单一来源）： [panopticon/agents.manifest.yaml](panopticon/agents.manifest.yaml)
- 生成工具： [panopticon/tools/generate_panopticon.py](panopticon/tools/generate_panopticon.py)
- 校验工具： [panopticon/tools/validate_panopticon.py](panopticon/tools/validate_panopticon.py)

另外新增：

- Mission Control env_file： [panopticon/env/mission-control.env.example](panopticon/env/mission-control.env.example)
- Mission Control UI env_file： [panopticon/env/mission-control-ui.env.example](panopticon/env/mission-control-ui.env.example)

## 快速启动

推荐流程（Manifest 驱动）：

1. 安装工具依赖：

```bash
pip install -r panopticon/tools/requirements.txt
```

1. 编辑 [panopticon/agents.manifest.yaml](panopticon/agents.manifest.yaml)

1. 生成 compose 与 env：

```bash
python panopticon/tools/generate_panopticon.py --prune
```

1. 校验配置：

```bash
python panopticon/tools/validate_panopticon.py
```

可选：指定数据根目录（方便把数据放到 U 盘 / 外接 SSD / 树莓派挂载点）。

- 复制模板： [panopticon/.env.example](panopticon/.env.example) → `panopticon/.env`
- 修改 `PANOPTICON_DATA_DIR`：
  - Linux / Raspberry Pi：`/mnt/usb/panopticon-data`
  - Windows（Docker Desktop）：`E:/panopticon-data`

首次搬移到 U 盘/新磁盘后，建议先创建数据目录（等价于 `mkdir -p`）：

Linux / Raspberry Pi（bash）：

```bash
export PANOPTICON_DATA_DIR=/mnt/usb/panopticon-data

mkdir -p \
  "$PANOPTICON_DATA_DIR/mission-control/postgres-data" \
  "$PANOPTICON_DATA_DIR/mission-control/redis-data" \
  "$PANOPTICON_DATA_DIR/agent-homes/nox" \
  "$PANOPTICON_DATA_DIR/agent-homes/metrics" \
  "$PANOPTICON_DATA_DIR/agent-homes/email" \
  "$PANOPTICON_DATA_DIR/agent-homes/growth" \
  "$PANOPTICON_DATA_DIR/agent-homes/trades" \
  "$PANOPTICON_DATA_DIR/agent-homes/health" \
  "$PANOPTICON_DATA_DIR/agent-homes/writing" \
  "$PANOPTICON_DATA_DIR/agent-homes/personal" \
  "$PANOPTICON_DATA_DIR/workspaces/nox" \
  "$PANOPTICON_DATA_DIR/workspaces/metrics" \
  "$PANOPTICON_DATA_DIR/workspaces/email" \
  "$PANOPTICON_DATA_DIR/workspaces/growth" \
  "$PANOPTICON_DATA_DIR/workspaces/trades" \
  "$PANOPTICON_DATA_DIR/workspaces/health" \
  "$PANOPTICON_DATA_DIR/workspaces/writing" \
  "$PANOPTICON_DATA_DIR/workspaces/personal"
```

Windows（PowerShell）：

```powershell
$env:PANOPTICON_DATA_DIR = 'E:/panopticon-data'

$dirs = @(
  'mission-control/postgres-data',
  'mission-control/redis-data',
  'agent-homes/nox','agent-homes/metrics','agent-homes/email','agent-homes/growth',
  'agent-homes/trades','agent-homes/health','agent-homes/writing','agent-homes/personal',
  'workspaces/nox','workspaces/metrics','workspaces/email','workspaces/growth',
  'workspaces/trades','workspaces/health','workspaces/writing','workspaces/personal'
)

$dirs | ForEach-Object {
  $path = Join-Path $env:PANOPTICON_DATA_DIR $_
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}
```

1. 编辑 8 份 env 模板（至少填 MODEL_ID / BASE_URL / API_KEY / OPENCLAW_GATEWAY_TOKEN）：

- [panopticon/env/nox.env.example](panopticon/env/nox.env.example)
- [panopticon/env/metrics.env.example](panopticon/env/metrics.env.example)
- [panopticon/env/email.env.example](panopticon/env/email.env.example)
- [panopticon/env/growth.env.example](panopticon/env/growth.env.example)
- [panopticon/env/trades.env.example](panopticon/env/trades.env.example)
- [panopticon/env/health.env.example](panopticon/env/health.env.example)
- [panopticon/env/writing.env.example](panopticon/env/writing.env.example)
- [panopticon/env/personal.env.example](panopticon/env/personal.env.example)

1. 启动：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d
```

1. 查看日志：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml logs -f --tail=200
```

## 增删 Agent 快速作业

新增 agent（建议）：

1. 在 [panopticon/agents.manifest.yaml](panopticon/agents.manifest.yaml) 新增一项：

- `slug`（全小写）
- `gateway_host_port` / `bridge_host_port`（不可冲突）
- `gateway_token`
- `enabled: true`

1. 运行：

```bash
python panopticon/tools/generate_panopticon.py --prune
python panopticon/tools/validate_panopticon.py
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build
```

下线/删除 agent：

1. 将该 agent 设为 `enabled: false`（或从 manifest 删除）

1. 运行：

```bash
python panopticon/tools/generate_panopticon.py --prune
python panopticon/tools/validate_panopticon.py
docker compose -f panopticon/docker-compose.panopticon.yml up -d --remove-orphans
```

1. 如需释放数据空间，手动删除 `${PANOPTICON_DATA_DIR:-.}/agent-homes/<slug>` 与 `${PANOPTICON_DATA_DIR:-.}/workspaces/<slug>`。

## 端口映射（host → container）

Mission Control：

- API：18910→8080（REST + WebSocket）
- UI：18920→8050（Dash）

- nox：18801→18789，18802→18790
- metrics：18811→18789，18812→18790
- email：18821→18789，18822→18790
- growth：18831→18789，18832→18790
- trades：18841→18789，18842→18790
- health：18851→18789，18852→18790
- writing：18861→18789，18862→18790
- personal：18871→18789，18872→18790

Mission Control API（示例）：

```bash
# 健康检查
curl http://localhost:18910/health

# 读取看板
curl http://localhost:18910/v1/boards/default

# 产生日志事件（可选）
curl -X POST http://localhost:18910/v1/events \
  -H "Content-Type: application/json" \
  -d '{"type":"agent.heartbeat","agent":"nox","payload":{"ok":true}}'
```

## 数据隔离

- 每个 agent 的 OpenClaw home：`${PANOPTICON_DATA_DIR:-.}/agent-homes/<agent>`
- 每个 agent 的 workspace：`${PANOPTICON_DATA_DIR:-.}/workspaces/<agent>`（挂载到容器内 `/home/node/.openclaw/workspace`）
- Mission Control 数据：`${PANOPTICON_DATA_DIR:-.}/mission-control/*`

## 注意事项

- 该 compose 默认从本 repo 直接 build CN-IM 镜像：`../src/OpenClaw-Docker-CN-IM`（tag 为 `openclaw-docker-cn-im:local`）；首次启动会花较久时间在安装依赖与插件。
- `OPENCLAW_GATEWAY_PORT` / `OPENCLAW_BRIDGE_PORT` 在 env 中保持 **18789/18790**（容器内端口固定）；host 端口在 compose 中已做区分。

Mission Control：

- 默认不启用鉴权；如需简单鉴权可在 [panopticon/env/mission-control.env.example](panopticon/env/mission-control.env.example) 设置 `MC_AUTH_TOKEN`，并在请求加上 `Authorization: Bearer <token>`。
