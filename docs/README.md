# 文档索引

这个目录只做一件事：帮你快速找到正确文档，而不是让你在一堆大部头里来回跳转。

## 先建立系统地图

如果你不是在找某一篇专题，而是想先理解“个人 AI 基础设施”这套东西由什么组成，按下面顺序读最快：

1. [../README.md](../README.md)：先选路，理解单 Agent、Panopticon、Mission Control 各自解决什么问题。
2. [../panopticon/README.md](../panopticon/README.md)：看主路线的运行态、env、Compose 和日常运维入口。
3. [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md)：看控制面、事件流、同源网关和治理边界。
4. [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md)：看资料导入、治理、resolve 与审计链路。

## 按建设阶段找文档

| 你现在在搭哪一层 | 先读什么 | 读完会知道什么 |
| --- | --- | --- |
| 接入与配置层 | [../README.md](../README.md) + [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) | 怎么先把模型、渠道和 `openclaw.json` 跑通 |
| Agent 运行层 | [../panopticon/README.md](../panopticon/README.md) | 8-Agent 主路线怎么启动、校验和运维 |
| 控制面 | [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md) | Mission Control UI、API、网关和部署边界怎么协作 |
| 知识治理层 | [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) + [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md) | 资料怎么进入知识系统，以及 8-Agent 怎么统一走评估链路 |

## 先按角色选入口

| 你现在要做什么 | 先读什么 |
| --- | --- |
| 第一次安装并想快速核对步骤 | [new-user-15-minute-install-checklist-zh-cn.md](new-user-15-minute-install-checklist-zh-cn.md) |
| 第一次安装 OpenClaw | [../README.md](../README.md) |
| 搭建 8-Agent 主路线 | [../panopticon/README.md](../panopticon/README.md) |
| 准备升级或回滚 Panopticon OpenClaw 运行态 | [openclaw-cli-cheatsheet-zh-cn.md](openclaw-cli-cheatsheet-zh-cn.md) |
| 需要日常不停机备份、定期全量备份或 U 盘迁移 | [openclaw-backup-retention-zh-cn.md](openclaw-backup-retention-zh-cn.md) |
| 需要从局域网电脑访问 Mission Control / Web Chat | [mission-control-lan-access-zh-cn.md](mission-control-lan-access-zh-cn.md) |
| 理解 Mission Control 的落地方式 | [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md) |
| 理解知识系统导入与治理 | [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) |
| 想先理解 Inner-Map 是什么、何时用、怎么和评估链路配合 | [inner-map-session-acceptance-zh-cn.md](inner-map-session-acceptance-zh-cn.md) |
| 想看任务编排模板和具体示例 | [task-orchestration-templates-zh-cn.md](task-orchestration-templates-zh-cn.md) |
| 需要一份 CLI 生命周期速查表 | [openclaw-cli-cheatsheet-zh-cn.md](openclaw-cli-cheatsheet-zh-cn.md) |
| 配飞书消息渠道 | [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md) |
| 看 openclaw.json 实际写法 | [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) |
| 准备联调真实语音设备 | [voice-device-bringup-zh-cn.md](voice-device-bringup-zh-cn.md) |
| 看英文概览 | [mission-control-overview-en.md](mission-control-overview-en.md) |

## 推荐阅读顺序

### 新用户

1. [new-user-15-minute-install-checklist-zh-cn.md](new-user-15-minute-install-checklist-zh-cn.md)
2. [../README.md](../README.md)
3. [../panopticon/README.md](../panopticon/README.md)
4. [openclaw-cli-cheatsheet-zh-cn.md](openclaw-cli-cheatsheet-zh-cn.md)
5. [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)
6. [voice-device-bringup-zh-cn.md](voice-device-bringup-zh-cn.md)

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
| [mission-control-lan-access-zh-cn.md](mission-control-lan-access-zh-cn.md) | 局域网访问 Control UI / Web Chat 指南 | 需要从另一台设备访问 `18920` 时 |
| [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md) | 8-Agent 共用评估调用规范 | 统一 resolve / review 契约时 |
| [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md) | 中文落地手册 | 想按工程视角搭系统时 |
| [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) | 知识系统实施手册 | 做资料导入、chunk、policy、resolve 时 |
| [inner-map-session-acceptance-zh-cn.md](inner-map-session-acceptance-zh-cn.md) | Inner-Map 使用说明与验收入口 | 想先理解 Inner-Map，再进入正式验收时 |
| [task-orchestration-templates-zh-cn.md](task-orchestration-templates-zh-cn.md) | 任务编排模板与具体示例 | 想提升任务写法、分工和交接体验时 |
| [openclaw-cli-cheatsheet-zh-cn.md](openclaw-cli-cheatsheet-zh-cn.md) | CLI 全流程速查表 | 需要命令总览、版本对齐、升级回滚与运维基线时 |
| [openclaw-backup-retention-zh-cn.md](openclaw-backup-retention-zh-cn.md) | 备份、迁移与保留策略 | 需要 U 盘迁移、日常增量、全量冷备或升级前后基线时 |
| [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md) | 飞书接入指南 | 配置渠道时 |
| [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) | 新手配置说明 | 需要手动理解配置项时 |
| [voice-device-bringup-zh-cn.md](voice-device-bringup-zh-cn.md) | 真实语音设备联调指南 | 接真实设备、排查 ROS2 话题和 live 事件时 |
| [mission-control-overview-en.md](mission-control-overview-en.md) | 英文总览 | 面向英文读者或补充背景时 |
| [mission-control-personal-panopticon-zh-hant.md](mission-control-personal-panopticon-zh-hant.md) | 繁中完整记录 | 需要完整方法论与归档材料时 |

## 使用原则

- 根 README 负责选路，不负责展开全部细节。
- Panopticon README 负责主路线启动与运维。
- 专题文档负责某一块的深入说明，不重复写安装入口。
- 当行为与代码不一致时，以当前仓库的 compose、脚本和实现为准。
