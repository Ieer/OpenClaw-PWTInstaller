# OpenClaw-PWTInstaller

<p align="center">
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-green.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Main%20Route-Panopticon%20%2B%20Mission%20Control-blue.svg" alt="Main Route">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

> 把 OpenClaw 从“单个助手”升级为可长期运行、可观测、可治理的个人 AI 基础设施。

<p align="center">
  <img src="photo/menu.png" alt="OpenClaw 配置中心" width="680">
</p>

## 这是什么

这个仓库提供三件事：

- 单 Agent 命令行安装器，适合先把 OpenClaw 跑起来。
- 8-Agent Panopticon 编排，适合长期运行多角色 Agent。
- Mission Control 控制台与 API，适合统一观察、治理和扩展整套系统。

如果你第一次接触 OpenClaw，先用“单 Agent”；如果你的目标是 PWT、多 Agent 长时运行或 Mission Control，看“Panopticon 主路线”。

## 先选路径

| 路线 | 适合谁 | 入口 | 状态 |
| --- | --- | --- | --- |
| 单 Agent 命令行 | 先跑通模型和消息渠道 | [install.sh](install.sh) | 稳定、轻量 |
| 8-Agent Panopticon | 长期运行、分工协作、统一治理 | [panopticon/README.md](panopticon/README.md) | 当前主路线 |
| Mission Control 二次开发 | 想改控制台、事件流、知识系统 | [mission_control_api/README.md](mission_control_api/README.md) | 已集成进主路线 |
| 根目录单容器 Docker | 本地临时实验 | [docker-compose.yml](docker-compose.yml) | 实验性，不建议作为默认部署 |

## 5 分钟上手

### 路线 A：单 Agent

```bash
git clone https://github.com/Ieer/OpenClaw-PWTInstaller.git
cd OpenClaw-PWTInstaller
chmod +x install.sh config-menu.sh
./install.sh
```

安装完成后建议立即验证：

```bash
openclaw models status
openclaw health
openclaw dashboard --no-open
```

### 路线 B：8-Agent Panopticon

```bash
git clone https://github.com/Ieer/OpenClaw-PWTInstaller.git
cd OpenClaw-PWTInstaller

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

启动后主要入口：

- Mission Control UI：<http://127.0.0.1:18920/>
- 同源 Chat：<http://127.0.0.1:18920/chat/nox/>
- API 健康检查：<http://127.0.0.1:18910/health>

## 系统要求

| 项目 | 建议 |
| --- | --- |
| 操作系统 | macOS 12+ / Ubuntu 20.04+ / Debian 11+ |
| Node.js | 22+ |
| Docker / Docker Compose | 使用 Panopticon 时必需 |
| Python | 3.11+，用于生成和校验脚本 |
| 内存 | 单 Agent 2GB+，Panopticon 建议 4GB+ |
| 磁盘 | 单 Agent 1GB+，Panopticon 建议 5GB+ |

## 你会得到什么

- 多模型接入：Claude、OpenAI、Gemini、OpenRouter、Ollama 等。
- 多渠道接入：Telegram、Discord、Feishu、WhatsApp。
- 多 Agent 运行时：nox、metrics、email、growth、trades、health、writing、personal。
- 统一控制面：Mission Control UI、事件流、任务板、同源聊天入口。
- 知识系统：原始资料导入、切片、OCR、validation policy、resolve、审计与回流。
- 工程化工具：manifest 生成、skills 校验、最小 CI gate、专项验证脚本。

<p align="center">
  <img src="photo/MissionControl.png" alt="Mission Control 控制台" width="49%">
  <img src="photo/AgentChat.png" alt="Agent Chat 界面" width="49%">
</p>

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| [install.sh](install.sh) | 单 Agent 一键安装 |
| [config-menu.sh](config-menu.sh) | 交互式配置中心 |
| [panopticon/](panopticon/) | 8-Agent 编排、env、模板、数据目录约定 |
| [mission_control_api/](mission_control_api/) | Mission Control 后端与知识系统接口 |
| [MissionControl/](MissionControl/) | Mission Control 前端 |
| [docs/](docs/) | 方法论、落地手册和专题说明 |
| [tools/](tools/) | 回归脚本、发布工具、专项验收 |

## 文档入口

按目标阅读，不要从头到尾硬啃：

| 你的目标 | 先读什么 |
| --- | --- |
| 第一次进入仓库，想 15 分钟跑通最小安装 | [docs/new-user-15-minute-install-checklist-zh-cn.md](docs/new-user-15-minute-install-checklist-zh-cn.md) |
| 快速安装单 Agent | [README.md](README.md) 当前页 + [docs/openclaw-json-guide-zh-cn.md](docs/openclaw-json-guide-zh-cn.md) |
| 搭建 8-Agent 主路线 | [panopticon/README.md](panopticon/README.md) |
| 理解 Mission Control 工程设计 | [docs/mission-control-playbook-zh-cn.md](docs/mission-control-playbook-zh-cn.md) |
| 理解知识系统治理 | [docs/knowledge-system-playbook-zh-cn.md](docs/knowledge-system-playbook-zh-cn.md) |
| 配飞书消息渠道 | [docs/feishu-setup-zh-cn.md](docs/feishu-setup-zh-cn.md) |
| 浏览文档全索引 | [docs/README.md](docs/README.md) |
| 参与贡献 | [CONTRIBUTING.md](CONTRIBUTING.md) |

## 新用户常用命令

### 单 Agent

```bash
openclaw gateway start
openclaw gateway status
openclaw logs --follow
bash ./config-menu.sh
```

### Panopticon

```bash
docker compose -f panopticon/docker-compose.panopticon.yml ps
docker compose -f panopticon/docker-compose.panopticon.yml logs -f --tail=200
bash panopticon/tools/check_panopticon_services.sh
bash panopticon/tools/recover_mission_control_gateway.sh
```

## 安全边界

- 不要把主路线暴露到不可信网络，尤其是同源网关和自动配对链路。
- 不要提交本地 `.env`、API Key、Gateway Token 或导出的运行态数据。
- 高风险能力默认按显式开启处理，例如容器控制器和外部副作用动作。
- 生产环境的 schema 变更统一走 Alembic，不要在运行时补建表。

## 社区贡献

欢迎贡献文档、脚本、Panopticon 模板、Mission Control 改进和回归测试。

开始前请先看：

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [docs/README.md](docs/README.md)
- [panopticon/README.md](panopticon/README.md)

如果你只是修文档或补示例，也欢迎直接发 PR。对新用户最有价值的贡献通常是：

- 缩短上手路径。
- 补充失败场景与排障步骤。
- 明确默认行为、边界和不推荐做法。

## 常见问题

### 为什么推荐从 18920 访问聊天入口？

因为主路线依赖同源网关统一处理鉴权、Control UI 注入和 WebSocket 代理。直接访问 188xx 端口，常见后果是 `token missing`、`1008` 或 `pairing required`。

### 为什么根目录 Docker Compose 不是默认方案？

它适合本地快速实验，但不覆盖主路线里的多 Agent 编排、Mission Control 和治理能力。

### 文档太多，应该从哪开始？

只看与你目标直接相关的一条路径即可。当前页负责选路，详细落地看 [panopticon/README.md](panopticon/README.md) 和 [docs/README.md](docs/README.md)。

## 许可证与链接

- 许可证：MIT
- OpenClaw 官网：<https://clawd.bot>
- OpenClaw Manager：<https://github.com/miaoxworld/openclaw-manager>
- OpenClaw 主仓库：<https://github.com/openclaw/openclaw>
- 项目讨论区：<https://github.com/Ieer/OpenClaw-PWTInstaller/discussions>
