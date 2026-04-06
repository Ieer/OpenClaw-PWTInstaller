# 文档索引

这个目录只做一件事：帮你快速找到正确文档，而不是让你在一堆大部头里来回跳转。

## 先按角色选入口

| 你现在要做什么 | 先读什么 |
| --- | --- |
| 第一次安装并想快速核对步骤 | [new-user-15-minute-install-checklist-zh-cn.md](new-user-15-minute-install-checklist-zh-cn.md) |
| 第一次安装 OpenClaw | [../README.md](../README.md) |
| 搭建 8-Agent 主路线 | [../panopticon/README.md](../panopticon/README.md) |
| 理解 Mission Control 的落地方式 | [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md) |
| 理解知识系统导入与治理 | [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) |
| 配飞书消息渠道 | [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md) |
| 看 openclaw.json 实际写法 | [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) |
| 看英文概览 | [mission-control-overview-en.md](mission-control-overview-en.md) |

## 推荐阅读顺序

### 新用户

1. [new-user-15-minute-install-checklist-zh-cn.md](new-user-15-minute-install-checklist-zh-cn.md)
2. [../README.md](../README.md)
3. [../panopticon/README.md](../panopticon/README.md)
4. [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)

### 想长期运行多 Agent

1. [../panopticon/README.md](../panopticon/README.md)
2. [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md)
3. [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md)
4. [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md)

### 想理解设计背景

1. [mission-control-overview-en.md](mission-control-overview-en.md)
2. [mission-control-personal-panopticon-zh-hant.md](mission-control-personal-panopticon-zh-hant.md)

## 文档分工

| 文件 | 用途 | 何时阅读 |
| --- | --- | --- |
| [new-user-15-minute-install-checklist-zh-cn.md](new-user-15-minute-install-checklist-zh-cn.md) | 新用户最短安装清单 | 第一次进入仓库时 |
| [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md) | 8-Agent 共用评估调用规范 | 统一 resolve / review 契约时 |
| [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md) | 中文落地手册 | 想按工程视角搭系统时 |
| [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) | 知识系统实施手册 | 做资料导入、chunk、policy、resolve 时 |
| [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md) | 飞书接入指南 | 配置渠道时 |
| [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) | 新手配置说明 | 需要手动理解配置项时 |
| [mission-control-overview-en.md](mission-control-overview-en.md) | 英文总览 | 面向英文读者或补充背景时 |
| [mission-control-personal-panopticon-zh-hant.md](mission-control-personal-panopticon-zh-hant.md) | 繁中完整记录 | 需要完整方法论与归档材料时 |

## 使用原则

- 根 README 负责选路，不负责展开全部细节。
- Panopticon README 负责主路线启动与运维。
- 专题文档负责某一块的深入说明，不重复写安装入口。
- 当行为与代码不一致时，以当前仓库的 compose、脚本和实现为准。
