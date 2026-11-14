# Mission Control 局域网访问说明（简中）

> 适用对象：需要在同一局域网的另一台电脑、平板或手机上访问 Mission Control UI / Web Chat 的用户
>
> 文档目标：区分网络可达、HTTPS 安全上下文、Origin 白名单与原生设备配对
>
> 标签：mission-control, panopticon, lan-access, websocket, origin-allowlist

## 1. 先记住标准入口

OpenClaw 2026.11.3 的原生设备认证需要浏览器安全上下文。局域网 IP 的纯 HTTP 即使页面返回 200、WebSocket 返回 101，也不能视为完整登录成功。

当前主机已部署可选 HTTPS 入口：

- Mission Control UI：`https://192.168.1.3:18921/`
- 单 Agent Chat：`https://192.168.1.3:18921/chat/<agent>/`
- 原 `http://192.168.1.3:18920/` 保留用于兼容和诊断，不是原生远程认证的推荐入口。

### 首次在客户端信任证书

1. 从可信网络下载公开 CA：`http://192.168.1.3:18920/lan-ca.crt`。
2. 导入前核对 SHA-256 指纹：`B9:29:1E:99:83:71:72:A8:7B:8D:AA:38:A3:34:DA:90:E9:BC:47:EA:CC:02:88:09:1A:9B:C4:A4:C4:29:4E:94`。HTTP 下载本身不能证明证书身份，应通过本说明或服务器控制台等独立可信渠道核对。
3. Windows：导入当前用户的“受信任的根证书颁发机构”；macOS：在钥匙串导入并为 SSL 信任；Firefox 若不使用系统信任库，需在“证书颁发机构”导入。
4. iOS/iPadOS：安装证书描述文件后，在“关于本机 / 证书信任设置”启用完全信任；Android：在系统安全设置安装 CA，具体名称随厂商而异，部分受管浏览器可能不接受用户 CA。
5. 重新打开浏览器访问 HTTPS 地址，确认没有证书错误，再提交对应 agent 的原生 token，并完成新浏览器的设备配对。

只分发 `ca.crt`，绝不分发 `ca.key` 或 `server.key`。根证书会扩大客户端信任范围，只应安装自己管理且已核验的 CA；不再使用时删除。本次服务器证书有效期一年，CA 有效期十年，续期和主机 IP 变化后需重新签发匹配 SAN 的服务器证书。

### HTTPS 配置与维护

HTTPS 使用 [../panopticon/docker-compose.lan-https.yml](../panopticon/docker-compose.lan-https.yml) 覆盖，不直接编辑生成的主 Compose：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml \
  -f panopticon/docker-compose.lan-https.yml up -d --no-deps mission-control-gateway
```

后续重建网关时保留两个 `-f`，否则可能移除 HTTPS 端口和证书挂载。普通容器重启保留现有配置。该覆盖要求本机已有 `panopticon/mission-control/tls/{ca.crt,server.crt,server.key}`，这些运行态证书不入库；仅复制 Compose 到新主机不会自动生成证书。

严格验证 HTTPS 与全部 agent 的配置/WS 升级：

```bash
MISSION_CONTROL_SCHEME=https MISSION_CONTROL_GATEWAY_PORT=18921 \
MISSION_CONTROL_CA_CERT="$PWD/panopticon/mission-control/tls/ca.crt" \
HTTP_TIMEOUT=15 HTTP_RETRIES=1 \
bash panopticon/tools/check_mission_control_lan_access.sh
```

不要使用 `curl -k` 的结果代替证书验证。WS 101 也不能代替实际 token 认证和设备配对验收。

例如当前主机的局域网 IP 是 `192.168.1.3`，那么 nox 的标准入口就是：

```text
https://192.168.1.3:18921/chat/nox/
```

不要绕过代理直接访问 `188xx` 端口。进入 `/chat/<agent>/` 后，新版 UI 自动导航到 `/chat/<agent>/chat` 或具体会话路径是正常行为，不应将它误诊为路径错误。

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
  --origin https://192.168.1.3:18921 \
  --origin https://raspberrypi.local:18921
```

新版通常支持配置热加载，先通过官方 CLI 更新或检查日志确认生效。确需重建时逐个执行并等待就绪，不要在低内存主机上同时重启全部 agent：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --no-deps --force-recreate openclaw-nox
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
      "http://192.168.1.3:18920",
      "https://192.168.1.3:18921"
    ]
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
https://<网关主机局域网IP>:18921/chat/<agent>/
```

例如：

```text
https://192.168.1.3:18921/chat/nox/
```

如果你在网关主机本机用 `curl http://127.0.0.1:18920/...` 做验证，Nginx 会把 `127.0.0.1` 重定向到 `localhost`。这只适合验证本机入口，不适合替代局域网 Origin 验证。

## 4. 常见错误与对应处理

### `ERR_CERT_AUTHORITY_INVALID`

客户端没有信任本部署的 CA。按第 1 节导入公开根证书并核对指纹，重新打开浏览器。不要通过关闭 TLS 验证或设备认证来解决。客户端信任完成之前，不能宣称该客户端的 HTTPS 登录和对话已经验收。

### JavaScript 资源 500/502 或一直 Loading

本次实测代理将无请求体 GET 转发为分块请求时，上游会间歇中断大资源响应。API 已修复空 GET/HEAD 的 `Transfer-Encoding` 处理，并对幂等请求的瞬态读取失败最多重试一次，写请求不重试。更新镜像后仍失败应检查 API 错误、资源状态和主机内存，而不是盲目轮换 token。

### `origin not allowed`

根因通常只有一个：浏览器实际 Origin 不在 `allowedOrigins` 列表里。

优先检查：

1. 地址栏里实际是 IP、主机名还是 localhost
2. 白名单里的 `scheme / host / port` 是否完全一致
3. 访问路径是否从标准入口 `/chat/<agent>/` 进入，以及是否漏了 HTTPS 的 `18921` Origin

### `token missing` 或 `disconnected (1008)`

这通常不是 Origin 白名单问题，而是以下几类问题：

1. 绕过了 `18920` 同源入口
2. gateway token 不一致
3. 配对状态或 trusted proxies 配置不一致

不要为诊断随意轮换全部 token。使用对应 agent 的原生认证入口，精确匹配当前浏览器设备 ID 与待批准请求 ID 后，只批准该条请求：

```bash
docker exec --user node openclaw-nox openclaw devices approve <request-id>
```

### 页面能打开，但聊天不连通

优先排查：

1. 是否为受信任 HTTPS 安全上下文；浏览器控制台 `isSecureContext`、`!!crypto.subtle` 应为 `true`
2. 是否访问了 `188xx` 端口而不是 `18920`
3. `allowedOrigins` 是否只写了 localhost

## 5. 安全边界

保留原生 token、设备签名和显式设备配对。新版已移除历史认证绕过配置，不要再写入 `allowInsecureAuth` 或 `dangerouslyDisableDeviceAuth`。不能把忽略证书警告当作建立可信 HTTPS。

代理信任同样必须精确：API 的 `MC_CHAT_TRUSTED_PROXY_IPS` 指向 nginx 实际 IP，各 agent 的 `gateway.trustedProxies` 指向 API 实际 IP。容器/网络重建后应重新核对，不能用信任整个 Docker 子网解决地址漂移。

额外提醒：

- 不要把 `18920` 或 `18921` 直接暴露到不可信公网
- 不要把 `allowedOrigins` 配成 `*`
- 如果后续需要更稳妥的远程访问，优先考虑 HTTPS 或 Tailscale Serve

## 6. 相关文档

- 主路线启动与运维： [../panopticon/README.md](../panopticon/README.md)
- `openclaw.json` 字段说明： [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)
- Mission Control 工程背景： [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md)
