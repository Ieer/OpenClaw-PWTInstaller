# Multi-Agent Portability Assessment

## 通用性结论

`openclaw-self-heal` 可以推广到所有 Panopticon agent，但需要区分三层能力：

1. **平台通用层**：所有 agent 共享，直接复用。
2. **Agent 通用层**：按 agent slug 参数化生成。
3. **Agent 专属层**：由各 agent 自己声明，不应从 nox 直接复制。

当前 nox 首版实现的通用度约为 **7.5/10**。如果其他 agent 通过 scaffold 生成 registry、复制通用 runner，并只补自己的专属 item，可提升到 **8.5/10**。

## 可直接通用的项目

| Item 类型 | 通用性 | 说明 |
| --- | --- | --- |
| Mission Control `/health` | 高 | 所有 agent 共享同一控制面 |
| Agent endpoint probe | 高 | 只需替换 agent slug |
| Workspace contract | 高 | 所有 workspace 都有相同目录契约 |
| Release dry-run | 高 | rollout 脚本支持传入 agent slug |
| Rollback metadata readiness | 高 | 共享 `.release-state` |
| State queue scan | 中高 | 路径一致，但语义可能因 agent 角色不同而变 |

## 需要参数化的项目

| 字段 | nox 示例 | 其他 agent 规则 |
| --- | --- | --- |
| `owner_scope` | `nox` | 替换为目标 agent slug |
| endpoint item id | `agent.nox_endpoint` | `agent.<slug>_endpoint` |
| endpoint command | `check_agent_endpoints.sh nox` | `check_agent_endpoints.sh <slug>` |
| workspace contract | `--agents nox` | `--agents <slug>` |
| release dry-run | `--dry-run nox` | `--dry-run <slug>` |
| state path | `memory/heartbeat-state.json` | 每个 workspace 自己的 memory |

## 不应盲目通用的 nox 专属项目

| Item | 原因 | 推广方式 |
| --- | --- | --- |
| `rokid.plugin_bundle` | Rokid link/config 是 nox 专属硬件集成 | 仅目标 agent 明确接入 Rokid 时复制 |
| `bypy.token_connectivity` | token 与云盘路径涉及个人凭据 | 作为 L3 模板，需每个 agent 独立 Review |
| `wjx.cli_config` | 问卷星 API key 与业务权限敏感 | 作为 L3 模板，需每个 agent 独立配置 |
| Python Pillow 离线恢复 | 依赖 `/mnt/usb/scripts/restore-python-pkgs.sh` | 只作为可选 runtime item，不默认 repair |

## 其他 agent 建议首批 item

每个 agent 的首批通用 registry 应只包含低风险项：

- `workspace.state_queue`
- `workspace.contract`
- `mission_control.api_health`
- `agent.<slug>_endpoint`
- `release.preflight_dry_run`
- `release.rollback_readiness`

然后按角色添加专属项：

- `metrics`：数据源、报表脚本、数据库只读连接。
- `email`：邮件 provider、SMTP/API token、退订/发送保护。
- `growth`：实验配置、数据看板、广告/渠道 API。
- `trades`：行情数据、风控阈值、交易动作 Review Gate。
- `health`：健康数据源、隐私文件、提醒通道。
- `writing`：PPT/docx/xlsx/image/OCR 依赖、字体与渲染工具。
- `personal`：日程、文件同步、个人隐私集成。

## 推广门槛

把 self-heal 推广到其他 agent 前，至少满足：

1. 目标 agent 在 `agents.manifest.yaml` 中 enabled。
2. `check_agent_endpoints.sh <slug>` 通过或能给出明确降级原因。
3. `test_workspace_contract.py --agents <slug>` 通过。
4. registry 中没有 nox 专属 token、Rokid、ByPy、wjx 配置。
5. L2/L3/L4 item 明确 Review Gate、冷却和最大尝试次数。
6. runner dry-run 通过，且不会写 token 明文。

## 推荐迁移方式

使用 `scripts/scaffold_agent_self_heal.py --agent <slug>` 为目标 agent 生成 workspace skill 骨架和通用 registry。首版只启用 L0/L1 诊断；确认稳定后再加入专属 repair item。
