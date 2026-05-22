# Mission Control 局域网访问说明（简中）

> 适用对象：需要在同一局域网的另一台电脑、平板或手机上访问 Mission Control UI / Web Chat 的用户
>
> 文档目标：说明 `origin not allowed` 的根因，并给出 Panopticon 主路线下更稳定的局域网访问方法
>
> 标签：mission-control, panopticon, lan-access, websocket, origin-allowlist

## 1. 先记住标准入口

局域网访问时，统一从 `18920` 的同源入口进入：

- Mission Control UI：`http://<网关主机局域网IP>:18920/`
- 单 Agent Chat：`http://<网关主机局域网IP>:18920/chat/<agent>/`

例如当前主机的局域网 IP 是 `192.168.1.3`，那么 nox 的标准入口就是：

```text
http://192.168.1.3:18920/chat/nox/
```

不要直接访问 `188xx` 端口，也不要把聊天地址写成 `/chat/<agent>/chat`。当前仓库主路线的标准入口只有 `/chat/<agent>/`。

## 2. 为什么会报 `origin not allowed`

Panopticon 的链路是：

1. 浏览器访问 `mission-control-gateway` 的 `18920`
2. `/chat/` 请求被代理到 `mission-control-api`
3. `mission-control-api` 再把浏览器的 `Origin` 透传给上游 OpenClaw gateway
4. OpenClaw gateway 根据 `gateway.controlUi.allowedOrigins` 做精确匹配

这意味着：

- 地址栏里最终显示什么 `scheme + host + port`，上游就会校验什么 Origin
- `http://localhost:18920`、`http://192.168.1.3:18920`、`http://raspberrypi.local:18920` 是三个不同的 Origin
- 只放开 `localhost`，并不会自动放开局域网 IP 或主机名

当前 nox 的实际配置文件是 [../panopticon/agent-homes/nox/openclaw.json](../panopticon/agent-homes/nox/openclaw.json)。

## 3. 标准配置步骤

### 步骤 1：确认网关主机的局域网地址

在网关主机上执行：

```bash
hostname -I
ip -brief addr
```

记录你真正希望用户访问的地址。

如果你最终让用户通过下面任何一种地址访问，就必须把对应 Origin 精确加入白名单：

- `http://192.168.1.3:18920`
- `http://192.168.8.128:18920`
- `http://raspberrypi.local:18920`

### 步骤 2：自动同步精确 Origin

推荐先用仓库工具把当前网关主机的 LAN IP、主机名和 `.local` 入口同步到所有 agent：

```bash
python panopticon/tools/sync_mission_control_lan_origins.py
```

如果你还会通过其他固定地址访问，可以显式追加：

```bash
python panopticon/tools/sync_mission_control_lan_origins.py \
  --origin http://192.168.1.3:18920 \
  --origin http://raspberrypi.local:18920
```

同步后重建 agent 容器让 OpenClaw 重新读取配置：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --force-recreate \
  openclaw-nox openclaw-metrics openclaw-email openclaw-growth \
  openclaw-trades openclaw-health openclaw-writing openclaw-personal
```

也可以先跑巡检，确认网关端口、容器健康和白名单是否一致：

```bash
bash panopticon/tools/check_mission_control_lan_access.sh
```

### 步骤 3：手工确认 `allowedOrigins`

以 nox 为例，编辑 [../panopticon/agent-homes/nox/openclaw.json](../panopticon/agent-homes/nox/openclaw.json)，在 `gateway.controlUi.allowedOrigins` 中加入实际入口：

```json
"gateway": {
  "port": 26216,
  "mode": "local",
  "bind": "lan",
  "controlUi": {
    "allowedOrigins": [
      "http://127.0.0.1:18920",
      "http://localhost:18920",
      "http://192.168.1.3:18920"
    ],
    "allowInsecureAuth": true,
    "dangerouslyDisableDeviceAuth": true
  }
}
```

如果你会同时通过多个入口访问，就把这些入口全部列进去，但都必须是完整 Origin。

不要这样做：

- 不要写成 `*`
- 不要误以为放开 `localhost` 就等于放开局域网 IP
- 不要依赖 `/chat/<agent>/chat`

### 步骤 4：重建对应 agent 容器

修改配置后，重建对应 agent 容器让 OpenClaw 重新加载配置：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --force-recreate openclaw-nox
```

如果你改的是其他 agent，就把 `openclaw-nox` 替换成对应服务名。

### 步骤 5：从局域网客户端验证标准入口

在局域网另一台机器上，直接访问：

```text
http://<网关主机局域网IP>:18920/chat/<agent>/
```

例如：

```text
http://192.168.1.3:18920/chat/nox/
```

如果你在网关主机本机用 `curl http://127.0.0.1:18920/...` 做验证，Nginx 会把 `127.0.0.1` 重定向到 `localhost`。这只适合验证本机入口，不适合替代局域网 Origin 验证。

## 4. 常见错误与对应处理

### `origin not allowed`

根因通常只有一个：浏览器实际 Origin 不在 `allowedOrigins` 列表里。

优先检查：

1. 地址栏里实际是 IP、主机名还是 localhost
2. 白名单里的 `scheme / host / port` 是否完全一致
3. 访问路径是否使用了标准入口 `/chat/<agent>/`

### `token missing` 或 `disconnected (1008)`

这通常不是 Origin 白名单问题，而是以下几类问题：

1. 绕过了 `18920` 同源入口
2. gateway token 不一致
3. 配对状态或 trusted proxies 配置不一致

可先执行：

```bash
bash panopticon/tools/rotate_gateway_tokens.sh
docker compose -f panopticon/docker-compose.panopticon.yml up -d --force-recreate mission-control-gateway
```

### 页面能打开，但聊天不连通

优先排查：

1. 是否用了错误路径 `/chat/<agent>/chat`
2. 是否访问了 `188xx` 端口而不是 `18920`
3. `allowedOrigins` 是否只写了 localhost

## 5. 安全边界

当前仓库示例通常保留：

- `allowInsecureAuth: true`
- `dangerouslyDisableDeviceAuth: true`

这能让纯 HTTP 的局域网控制台更容易跑通，但本质上属于更宽松的受信局域网配置，不适合不可信网络。

额外提醒：

- 不要把 `18920` 暴露到不可信公网
- 不要把 `allowedOrigins` 配成 `*`，除非只是临时受控测试
- 如果后续需要更稳妥的远程访问，优先考虑 HTTPS 或 Tailscale Serve

## 6. 相关文档

- 主路线启动与运维： [../panopticon/README.md](../panopticon/README.md)
- `openclaw.json` 字段说明： [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)
- Mission Control 工程背景： [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md)
