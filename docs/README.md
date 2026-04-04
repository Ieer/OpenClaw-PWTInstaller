# Docs 文档索引

本目录已按“主题 + 范围 + 语言”重新整理，避免旧文件名语义不清与重复阅读。

## 入口口径（与根 README 同步）

- **主推路线**：`8-Agent Panopticon + Mission Control`（平台化、长期运行、多 Agent 协作）。
- **次要路线**：`单 Agent 命令行安装器`（快速上手、轻量使用）。
- **实验性路线**：根目录 `docker-compose.yml` 单容器部署（非主推，不作为生产默认路径）。

若你要做长期运行与多 Agent 协作，请优先阅读：
- [../README.md](../README.md) 的“运行模式总览 / 快速开始”
- [../panopticon/README.md](../panopticon/README.md) 的“架构、启动与运维”

## 命名规则

- `mission-control-overview-en.md`：英文总览
- `mission-control-playbook-zh-cn.md`：简中工程落地手册
- `mission-control-personal-panopticon-zh-hant.md`：繁中完整备案
- `knowledge-system-playbook-zh-cn.md`：知识系统落地手册（普通 U 盘原始资料导入）
- `feishu-setup-zh-cn.md`：飞书接入指南
- `openclaw-json-guide-zh-cn.md`：`openclaw.json` 新手配置说明

命名格式统一为：`<topic>-<scope>-<locale>.md`

## 文档分工

| 文件 | 用途 | 重复检查结论 |
| --- | --- | --- |
| [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md) | 8-Agent 共用评估调用规范 | 固化 resolve 请求字段、调用时机与输出模板，避免规范散落在对话中 |
| [mission-control-overview-en.md](mission-control-overview-en.md) | Mission Control 英文概览 | 与中文文档保留互补关系，不再重复展开细节 |
| [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md) | 8-Agent 简中落地手册 | 保留执行导向内容，作为主入口 |
| [mission-control-personal-panopticon-zh-hant.md](mission-control-personal-panopticon-zh-hant.md) | 8-Agent 繁中完整备案 | 保留设计、治理、演示脚本等完整记录 |
| [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md) | 知识系统落地手册（简中） | 固化“普通 U 盘原始资料 + Mission Control 登记层”SOP |
| [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md) | 飞书渠道配置 | 独立主题，无重复合并需求 |
| [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) | `openclaw.json` 新手说明 | 基于当前仓库实际配置，补充本地 Ollama 正确示例 |

## 合并与去重结果

- 旧文件名 `my_mission_control.md`、`unmanned-company-playbook-zh-cn.md`、`mission-control.md`、`feishu-setup.md` 已统一重命名。
- `mission-control-playbook-zh-cn.md` 与 `mission-control-personal-panopticon-zh-hant.md` 主题相同，但面向不同读者：前者偏施工，后者偏归档，因此保留双文档，不再视为无效重复。
- 文档内部交叉引用已统一为相对路径，并修正到当前仓库真实目录。

## 推荐阅读顺序

1. [../README.md](../README.md)
2. [../panopticon/README.md](../panopticon/README.md)
3. [mission-control-playbook-zh-cn.md](mission-control-playbook-zh-cn.md)
4. [agent-evaluation-contract-zh-cn.md](agent-evaluation-contract-zh-cn.md)
5. [knowledge-system-playbook-zh-cn.md](knowledge-system-playbook-zh-cn.md)
6. [mission-control-personal-panopticon-zh-hant.md](mission-control-personal-panopticon-zh-hant.md)
7. [mission-control-overview-en.md](mission-control-overview-en.md)
8. [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md)
9. [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)