# 新用户 15 分钟安装清单

这份清单只服务一类人：第一次进入这个仓库，目标是 15 分钟内确认环境、选对路线、完成最小安装并做一次验证。

如果你已经明确要搭 8-Agent 主路线，读完本页后直接进入 [../panopticon/README.md](../panopticon/README.md)。

## 0. 先决定你走哪条路

不要一上来就看所有文档，先选路线：

- 只想先把 OpenClaw 跑起来：走“单 Agent 命令行”。
- 想长期运行、多 Agent 协作、接 Mission Control：走“8-Agent Panopticon”。
- 只想做本地容器实验：根目录 `docker-compose.yml` 可以用，但不是默认推荐路径。

## 1. 3 分钟环境检查

在仓库根目录前，先确认这些命令可用：

```bash
node -v
docker --version
docker compose version
python3 --version
```

最低建议：

- Node.js 22+
- Python 3.11+
- Docker / Docker Compose 可正常运行
- 单 Agent 至少 2GB 内存，Panopticon 建议 4GB+

如果你只准备跑单 Agent，Docker 不是强制项；如果你要走 Panopticon，Docker 是必需项。

## 2. 1 分钟拉代码

```bash
git clone https://github.com/Ieer/OpenClaw-PWTInstaller.git
cd OpenClaw-PWTInstaller
```

## 3. 5 分钟完成最小安装

### 路线 A：单 Agent 命令行

```bash
chmod +x install.sh config-menu.sh
./install.sh
```

安装过程中通常会完成：

- 环境检查
- OpenClaw 安装
- 模型配置
- 基础连接测试
- 服务启动

如果你需要进一步配置消息渠道，再执行：

```bash
bash ./config-menu.sh
```

### 路线 B：8-Agent Panopticon

```bash
python -m pip install -r panopticon/tools/requirements.txt

for example in panopticon/env/*.env.example; do
  target="${example%.example}"
  if [ ! -f "$target" ]; then
    cp "$example" "$target"
  fi
done

bash panopticon/tools/rotate_gateway_tokens.sh
python panopticon/tools/generate_panopticon.py --prune
python panopticon/tools/validate_panopticon.py
python panopticon/tools/validate_skills_template.py
docker compose -f panopticon/docker-compose.panopticon.yml up -d
```

在这条路上，你至少需要检查并填写：

- `panopticon/env/mission-control.env`
- `panopticon/env/nox.env`
- `panopticon/env/metrics.env`
- `panopticon/env/email.env`

最少要保证模型、Base URL、API Key 和 Gateway Token 已经不是占位值。

## 4. 3 分钟做最小验证

### 单 Agent 验证

```bash
openclaw models status
openclaw health
openclaw dashboard --no-open
```

### Panopticon 验证

```bash
docker compose -f panopticon/docker-compose.panopticon.yml ps
curl -fsS http://127.0.0.1:18910/health
curl -I http://127.0.0.1:18920/
```

推荐只从同源入口打开 Chat：

```text
http://127.0.0.1:18920/chat/nox/
```

不要直接访问 `188xx` 端口，否则很容易遇到 `token missing`、`1008` 或 `pairing required`。

## 5. 遇到问题先看哪里

- 单 Agent 安装或模型配置问题：回到 [../README.md](../README.md)
- 8-Agent 启动、网关、502、1008：看 [../panopticon/README.md](../panopticon/README.md)
- 飞书渠道配置：看 [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md)
- `openclaw.json` 写法：看 [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)
- 想系统性浏览所有文档：看 [README.md](README.md)

## 6. 新用户最容易踩的坑

- 一开始就试图同时看单 Agent、Panopticon、Mission Control 三条路径，结果信息过载。
- 忘记把 `*.env.example` 复制成本地 `*.env`。
- 没有轮换 Gateway token 就直接启动 Panopticon。
- 直接打开 `188xx` 端口排查聊天问题，而不是用 `18920/chat/<agent>/`。
- 把本地 `.env`、token 或运行态数据误提交到 Git。

## 7. 下一步怎么走

- 如果你刚跑通单 Agent：继续用 [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) 和 [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md) 补配置。
- 如果你刚跑通 Panopticon：继续看 [../panopticon/README.md](../panopticon/README.md) 的运维和排障章节。
- 如果你准备参与社区贡献：看 [../CONTRIBUTING.md](../CONTRIBUTING.md)。