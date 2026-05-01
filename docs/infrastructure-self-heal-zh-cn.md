# OpenClaw / Panopticon 基础设施自愈指南（简中）

本文说明当前仓库里的基础设施自愈设计：如何诊断、如何低风险修复、如何把未来新增自愈 item 标准化接入，以及如何把同一套能力推广到 8-Agent Panopticon。

> 原则：先诊断，后修复；先低风险，后高风险；所有凭证、外部服务、容器重启、发布/回滚动作必须有 Review Gate。

---

## 1. 自愈能力分层

基础设施自愈分三层：

| 层级 | 作用 | 当前落点 |
| --- | --- | --- |
| Global skill | 通用自愈协议、风险分级、item contract、多 agent 通用性 | [../panopticon/global-skills/openclaw-self-heal/SKILL.md](../panopticon/global-skills/openclaw-self-heal/SKILL.md) |
| Workspace skill | 每个 agent 自己的自愈清单、runner、状态文件 | [../panopticon/workspaces/nox/skills/self-heal/SKILL.md](../panopticon/workspaces/nox/skills/self-heal/SKILL.md) |
| Platform probes | Panopticon / Mission Control 的服务、端点、发布回滚检查 | [../panopticon/tools/check_panopticon_services.sh](../panopticon/tools/check_panopticon_services.sh)、[../panopticon/tools/check_agent_endpoints.sh](../panopticon/tools/check_agent_endpoints.sh) |

当前 agent 镜像基线还要求容器内具备 `python3`、`pip` 与 `PyYAML`。可用以下脚本巡检所有 agent：

```bash
bash panopticon/tools/check_agent_python_runtime.sh
```

如果该脚本失败，self-heal runner、`items.yaml` registry 和其他 Python/YAML 辅助脚本可能无法在 agent 容器内稳定运行；优先重建共享 `openclaw-docker-cn-im:local` 镜像并重建目标 `openclaw-*` 容器。

nox 的 Heartbeat 已接入 workspace self-heal runner，见 [../panopticon/workspaces/nox/HEARTBEAT.md](../panopticon/workspaces/nox/HEARTBEAT.md)。

---

## 2. 风险等级

所有自愈 item 必须归入一个风险等级：

| 等级 | 含义 | 默认策略 |
| --- | --- | --- |
| L0 | 只读诊断 | 总是允许 |
| L1 | 低风险本地修复 | 幂等、有超时、有 postcheck 时允许 |
| L2 | 容器/服务重启、运行态刷新 | 需要显式允许、冷却时间、最大次数、postcheck |
| L3 | token、外部服务、凭证相邻恢复 | 必须 Review-approved，并强制脱敏 |
| L4 | 发布、回滚、删除、覆盖、对外承诺、不可逆动作 | 默认只诊断；执行必须走独立 Review 决策 |

常见例子：

- L0：检查 Mission Control `/health`、检查 agent endpoint。
- L1：检查 workspace contract、创建缺失目录、导入 Python 包探针。
- L2：重启 `openclaw-nox` 容器。
- L3：恢复 ByPy token、wjx-cli API key。
- L4：执行 rollout、rollback、删除数据、对外发送。

---

## 3. nox 当前自愈入口

nox 当前 runner：

```bash
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py list-items
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py diagnose --max-level L1 --exit-zero
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py diagnose --item agent.nox_endpoint --exit-zero
```

nox 当前 registry：

- [../panopticon/workspaces/nox/skills/self-heal/items.yaml](../panopticon/workspaces/nox/skills/self-heal/items.yaml)

首批 item 覆盖：

| Item | 类型 | 风险 |
| --- | --- | --- |
| `python.pil_import` | Python 包导入 | L1 |
| `rokid.plugin_bundle` | Rokid 插件产物 | L2 |
| `bypy.token_connectivity` | ByPy token | L3 |
| `wjx.cli_config` | wjx-cli 安装与配置 | L3 |
| `workspace.state_queue` | state / Review gate 扫描 | L0 |
| `workspace.contract` | workspace 目录契约 | L1 |
| `mission_control.api_health` | Mission Control API 健康 | L0 |
| `agent.nox_endpoint` | nox Gateway / Bridge 端点 | L0 |
| `release.preflight_dry_run` | 发布 dry-run | L0 |
| `release.rollback_readiness` | 回滚 metadata 就绪性 | L0 |

---

## 4. Runner 行为

runner 固定生命周期：

1. 读取 `items.yaml`。
2. 校验 item schema。
3. 执行 probe。
4. 分类为 `ok` / `degraded` / `review_required`。
5. 如显式 repair，先检查风险门禁、冷却时间、最大尝试次数。
6. 执行 repair。
7. 执行 postcheck。
8. 更新 `memory/heartbeat-state.json`。
9. 输出 JSON 摘要。

支持命令：

```bash
python3 skills/self-heal/scripts/self_heal_runner.py list-items
python3 skills/self-heal/scripts/self_heal_runner.py diagnose
python3 skills/self-heal/scripts/self_heal_runner.py diagnose --item <item_id>
python3 skills/self-heal/scripts/self_heal_runner.py repair --item <item_id>
python3 skills/self-heal/scripts/self_heal_runner.py status
```

L2 修复需要：

```bash
python3 skills/self-heal/scripts/self_heal_runner.py repair --item <item_id> --allow-l2
```

L3/L4 或 `requires_review: true` 的修复需要：

```bash
python3 skills/self-heal/scripts/self_heal_runner.py repair --item <item_id> --review-approved
```

> 注意：即使带 `--review-approved`，L4 在当前 runner 中仍默认 diagnose-only；发布/回滚执行应使用专门 release runbook。

---

## 5. 新增自愈 item 的标准字段

每个 item 必须声明：

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定唯一 ID，例如 `agent.nox_endpoint` |
| `title` | 人类可读名称 |
| `category` | `runtime` / `plugin` / `token` / `service` / `release` / `storage` / `config` / `knowledge` / `external_api` / `workspace` |
| `owner_scope` | `global` / `mission_control` / `agent` / 具体 agent slug |
| `risk_level` | L0-L4 |
| `requires_review` | 是否必须 Review |
| `secret_policy` | `none` / `redact` / `review_only` / `forbidden` |
| `timeout_seconds` | 单项超时 |
| `cooldown_seconds` | 自动修复冷却 |
| `max_attempts_per_day` | 每日最大修复次数 |
| `dependencies` | 命令、文件、服务、挂载依赖 |
| `probe` | 只读诊断命令 |
| `repair` | 可选修复命令，必须幂等 |
| `postcheck` | 修复后验证命令 |
| `success_criteria` | 成功判定 |
| `rollback_hint` | 失败后的回退说明 |
| `evidence_paths` | 证据路径 |

最小 L0 示例：

```yaml
- id: agent.nox_endpoint
  title: nox Gateway and Bridge endpoints
  category: service
  owner_scope: nox
  risk_level: L0
  requires_review: false
  secret_policy: none
  timeout_seconds: 30
  cooldown_seconds: 0
  max_attempts_per_day: 0
  dependencies:
    files:
      - panopticon/tools/check_agent_endpoints.sh
  probe:
    command: bash panopticon/tools/check_agent_endpoints.sh nox
    cwd: repo
  success_criteria: nox gateway and bridge TCP endpoints are reachable.
  rollback_hint: Restart nox only after endpoint failure is confirmed and L2 policy is satisfied.
  evidence_paths:
    - panopticon/tools/check_agent_endpoints.sh
```

---

## 6. 多 Agent 通用性

`openclaw-self-heal` 可推广到所有 Panopticon agent，但必须分清三类 item：

| 类型 | 是否可通用 | 例子 |
| --- | --- | --- |
| 平台通用 | 可直接复用 | Mission Control `/health`、release dry-run、rollback metadata |
| Slug 参数化 | 替换 agent slug 后复用 | `agent.<slug>_endpoint`、workspace contract |
| Agent 专属 | 不应直接复制 | nox Rokid、ByPy token、wjx-cli、email SMTP、trades 风控 |

通用性详细评估见：

- [../panopticon/global-skills/openclaw-self-heal/references/multi-agent-portability.md](../panopticon/global-skills/openclaw-self-heal/references/multi-agent-portability.md)

### 为其他 agent 生成自愈骨架

先 dry-run：

```bash
python3 panopticon/global-skills/openclaw-self-heal/scripts/scaffold_agent_self_heal.py --agent metrics --dry-run
```

确认无误后生成：

```bash
python3 panopticon/global-skills/openclaw-self-heal/scripts/scaffold_agent_self_heal.py --agent metrics
```

默认生成低风险通用项：

- `workspace.state_queue`
- `workspace.contract`
- `mission_control.api_health`
- `agent.<slug>_endpoint`
- `release.preflight_dry_run`
- `release.rollback_readiness`

角色专属 item 应由对应 workspace 自己添加，并声明 Review Gate。

---

## 7. 与 Mission Control / Panopticon 的关系

基础设施自愈不替代现有巡检，而是把巡检结果纳入 item registry：

| 现有能力 | 自愈中的定位 |
| --- | --- |
| [../panopticon/tools/check_panopticon_services.sh](../panopticon/tools/check_panopticon_services.sh) | 平台层 health item 来源 |
| [../panopticon/tools/check_agent_endpoints.sh](../panopticon/tools/check_agent_endpoints.sh) | agent endpoint item 来源 |
| [../panopticon/tools/test_workspace_contract.py](../panopticon/tools/test_workspace_contract.py) | workspace contract item 来源 |
| [../tools/rollout_release_upgrade.py](../tools/rollout_release_upgrade.py) | release dry-run / version gate item 来源 |
| [../tools/rollback_release_upgrade.py](../tools/rollback_release_upgrade.py) | rollback readiness item 来源 |
| [../panopticon/agent-controller/app/main.py](../panopticon/agent-controller/app/main.py) | L2 容器控制入口，默认高风险 |

Mission Control 可通过 skills inventory 发现 global skill 与 workspace skill；后续可把 self-heal summary 接入 UI 面板。

---

## 8. 验收命令

校验 skill 文档：

```bash
python3 panopticon/tools/validate_skills_template.py
```

校验 global skill：

```bash
python3 panopticon/tools/validate_skills_template.py --skills-dir panopticon/global-skills
```

校验 runner 语法：

```bash
python3 -m py_compile panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py
```

校验 nox L0 诊断：

```bash
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py diagnose --max-level L0 --no-state --exit-zero
```

校验 L3 门禁：

```bash
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py repair --item bypy.token_connectivity --no-state
```

期望结果：命令拒绝执行 repair，并输出 `repair requires --review-approved`。

---

## 9. 操作边界

- 不把 token、API key、cookie、`Authorization`、`linkSecret` 写入日志。
- 不把 nox 专属 item 直接复制给其他 agent。
- 不在 Heartbeat 正文里继续堆自愈脚本；新增 item 走 registry。
- 不让 L2/L3/L4 自动循环重试。
- 不通过 self-heal 自动执行 rollout / rollback；只允许 dry-run 与 readiness 检查。
- 不绕过 Review Gate 执行外部服务恢复或对外承诺动作。

---

## 10. 当前成熟度

当前实现成熟度：约 **7.5/10**。

已具备：

- global skill 协议；
- nox workspace skill；
- item registry；
- runner；
- L2/L3/L4 门禁；
- token 脱敏；
- 多 agent 脚手架；
- dry-run 验证。

下一阶段目标：**8.5/10**。

需要补齐：

- registry 专用 validator；
- 每个 item 的 fixture 测试；
- Mission Control UI 展示 self-heal summary；
- 其他 agent 的低风险 registry scaffold；
- per-item 报告归档到 `artifacts/<task_id>/`。
