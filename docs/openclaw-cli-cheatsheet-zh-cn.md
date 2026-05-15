# OpenClaw CLI 全流程速查表（简中）

> 版本基线：OpenClaw 2026.4.29
>
> 仓库对齐原则：本仓库统一以 [../openclaw-release.yaml](../openclaw-release.yaml) 中的 `openclaw_version: 2026.4.29` 作为文档基线；当 CLI 外部资料与当前仓库脚本、compose、README 不一致时，以当前仓库实现为准。

---

## 这份速查表是干什么的

OpenClaw CLI 是 8 个 agent 通过命令行沟通的桥梁。

在这个仓库里，CLI 不是孤立存在的，它连接了几类工作：

- 单 Agent 初始化与本地调试
- 多 Agent 容器中的 gateway、health、logs 与模型检查
- 渠道绑定、配置修复、会话治理与故障排查
- Panopticon 与 Mission Control 迭代时的人机协同操作基线

这份 cheatsheet 按真实使用生命周期组织，目标不是覆盖所有子命令，而是给出一套在 OpenClaw 2026.4.29 上更稳定、便于系统迭代的命令视图。

## 先记住三条原则

1. 能用 CLI 改的，优先不要直接手改配置文件。
2. 遇到行为差异，先看 `openclaw --help`、`openclaw <group> --help`，再看仓库脚本和文档。
3. 在本仓库主路线里，运行结构以 [../panopticon/README.md](../panopticon/README.md) 和 [../README.md](../README.md) 为准，CLI 负责操作，不替代编排层。

## 1. 初始化与基础设置

第一次接触 OpenClaw，先把本地运行时、默认工作区和基础向导跑通。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw setup` | 初始化本地配置目录和默认工作区 | 常见于首次安装后的第一条命令 |
| `openclaw configure` | 启动交互式配置向导 | 适合绑定 API Key、模型和渠道 |
| `openclaw qr` | 生成移动端配对二维码 | 适合手机侧接管和监控 |
| `openclaw completion` | 生成 shell 自动补全脚本 | `source <(openclaw completion)` |
| `openclaw doctor` | 检查常见配置和运行问题 | 先诊断，再决定是否修复 |
| `openclaw doctor --fix` | 自动修复一部分可恢复问题 | 本仓库已有文档引用，适合配置异常时先试 |

本仓库补充：如果你走的是单 Agent 路线，首次安装入口优先看 [../README.md](../README.md) 的 install.sh 路线；CLI 更多用于安装后的校验与维护。

## 2. 配置与凭证管理

OpenClaw 2026.4.29 延续双层配置思路：全局配置与工作区 / agent 配置并存，局部优先。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw config get <key>` | 读取指定配置项 | `openclaw config get agents.defaults.model.primary` |
| `openclaw config set <key> <value>` | 非交互式写入配置 | `openclaw config set channels.feishu.requireMention false` |
| `openclaw config validate` | 验证配置合法性 | 本仓库文档已使用，适合排查 JSON 层级与字段错误 |
| `openclaw config reset <key>` | 恢复某一段配置到默认值 | `openclaw config reset agents.defaults` |
| `openclaw secrets ...` | 管理运行时敏感凭证 | 适合做热更新与避免明文扩散 |

对本仓库尤其重要：

- 单 Agent 常见配置文件位置说明见 [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md)
- Panopticon 不是“一份全局 openclaw.json 走天下”，而是每个 agent 独立 home 与独立配置
- 资料冲突时，以本仓库当前 manifest、env 与生成结果为准，不要从旧博客抄字段

## 3. 模型管理

模型是 agent 的“大脑”。这一层决定推理能力、成本和上下文窗口。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw models status` | 检查当前模型连通性和状态 | 本仓库根 README 已使用 |
| `openclaw models list` | 列出当前可用模型 | 适合确认 provider 与模型 ID |
| `openclaw models add` | 交互式添加模型 | 常见于首次接入新的 provider |
| `openclaw models pull <name>` | 拉取本地模型权重 | `openclaw models pull llama3:8b` |
| `openclaw models add-provider` | 交互式添加供应商 | 适合接入 OpenAI、Anthropic、Google、兼容网关 |
| `openclaw models set-default <name>` | 设置默认模型 | `openclaw models set-default gpt-4o` |
| `openclaw models inspect <name>` | 查看模型窗口和参数 | `openclaw models inspect gemini-1.5-pro` |

在本仓库里，模型配置常和以下内容联动：

- [openclaw-json-guide-zh-cn.md](openclaw-json-guide-zh-cn.md) 中的 `models` 与 `agents.defaults.model`
- Panopticon 下各 agent 的 env 覆盖
- Mission Control 知识系统的 embedding / generation provider 区分

## 4. Agent 管理

这是多 agent 运作的核心层。OpenClaw CLI 负责把不同 agent 注册、隔离、绑定到不同渠道与工作目录。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw agents add <name>` | 创建并注册 agent | `openclaw agents add ops-bot --workspace ~/.openclaw/ops` |
| `openclaw agents list` | 列出已注册 agent | 可配合 `--verbose` 或 `--format json` |
| `openclaw agents bind` | 将渠道流量绑定到某个 agent | `openclaw agents bind --agent ops-bot --bind telegram:ops` |
| `openclaw agents unbind` | 解除渠道绑定 | `openclaw agents unbind --agent ops-bot --all` |
| `openclaw agents set-identity` | 设置人设、头像、emoji | `openclaw agents set-identity --agent ops-bot --emoji "👷"` |
| `openclaw agent` | 触发单次 agent 交互 | `openclaw agent --agent ops-bot --message "汇总今日日志"` |

对本仓库的 8-Agent Panopticon，要额外注意：

- 当前主路线以容器隔离为主，不是把 8 个角色硬塞进同一个运行时
- agent 的职责边界、端口和运行目录以 [../panopticon/README.md](../panopticon/README.md) 为准
- CLI 更适合做 agent 行为验证、调试和应急操作，长期编排仍以 compose、manifest、env 为主

## 5. 渠道与消息互动

OpenClaw 的强项之一是把 agent 接入日常消息渠道。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw channels login` | 登录并连接新的消息渠道 | 常见于扫码登录场景 |
| `openclaw channels ...` | 查看、断开、管理已连接渠道 | 具体子命令以 `--help` 为准 |
| `openclaw message send` | 通过绑定渠道主动发消息 | `openclaw message send --channel telegram --target @username --message "Hi"` |

本仓库已落地的典型场景：

- 飞书配置参考 [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md)
- 常用排障命令包括 `openclaw gateway start`、`openclaw gateway status`、`openclaw logs --follow` 和 `openclaw doctor`

## 6. 技能与插件

Skill 决定 agent 能做什么，Plugin 决定系统能支持什么基础设施。

### Skills

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw skills list` | 查看已安装技能 | `openclaw skills list --agent ops-bot` |
| `openclaw skills install <name>` | 安装技能 | `openclaw skills install mcp-github` |
| `openclaw skills remove <name>` | 卸载技能 | `openclaw skills remove web-scraper` |
| `openclaw skills inspect <name>` | 检查权限与工具集 | 用于识别高危技能 |
| `openclaw skills grant` | 给 agent 授权技能 | `openclaw skills grant --agent ops-bot --skill mcp-github` |

### Plugins

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw plugins list` | 查看已安装插件 | 适合排查加载顺序和版本 |
| `openclaw plugins add <name>` | 安装插件 | `openclaw plugins add @openclaw/plugin-wechat-weipad` |
| `openclaw plugins enable <name>` | 启用插件 | `openclaw plugins enable custom-logger` |
| `openclaw plugins disable <name>` | 禁用插件 | 冲突排查时常用 |
| `openclaw plugins update --all` | 批量升级插件 | 更新前先记录版本 |

一句话辨析：

- Model 是大脑
- Skill 是手脚
- Plugin 是系统底座扩展

## 7. Gateway、运行态与日常运维

Gateway 是 OpenClaw 的心脏。对本仓库而言，这一层直接影响单 Agent 使用体验，也影响多 agent 容器的可观测性。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw gateway start` | 启动 gateway | 本仓库 README 与飞书文档已使用 |
| `openclaw gateway status` | 查看 gateway 状态 | 适合排查渠道是否在线 |
| `openclaw gateway restart` | 重启 gateway | 本仓库配置指南已使用 |
| `openclaw gateway run --port 18789` | 直接以指定端口前台运行 gateway | 适合临时调试或容器前台进程 |
| `openclaw gateway run --force` | 强制清理旧占用并前台启动 | 适合僵尸进程占口 |
| `openclaw logs --follow` | 跟踪运行日志 | 本仓库 README 与飞书文档已使用 |
| `openclaw health` | 查看整体健康度 | 本仓库根 README 已使用 |
| `openclaw status` | 查看系统状态 | 可用于补充渠道与运行态检查 |
| `openclaw dashboard --no-open` | 启动或展示 dashboard 而不自动打开浏览器 | 本仓库根 README 已使用 |
| `openclaw tui` | 启动终端 TUI | 适合观察 gateway、日志和对话流 |
| `openclaw sessions ...` | 管理会话上下文 | 适合清理长时记忆碎片 |
| `openclaw cron ...` | 管理定时任务 | 适合日报、巡检、定时汇总 |
| `openclaw system ...` | 管理系统事件与在线状态 | 适合连通性巡检 |

如果你在本仓库主路线中运维 8-Agent，除了 OpenClaw CLI，还应配合这些命令：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml ps
docker compose -f panopticon/docker-compose.panopticon.yml logs -f --tail=200
bash panopticon/tools/check_panopticon_services.sh
bash panopticon/tools/check_agent_python_runtime.sh
bash panopticon/tools/recover_mission_control_gateway.sh
```

这几条不是 OpenClaw CLI 子命令，但在当前仓库里是主路线运维事实来源。

`check_agent_python_runtime.sh` 会检查 8 个 `openclaw-*` 容器内的 `python3`、`pip` 和 `PyYAML`。当前 agent 镜像基线要求三者全部可用，否则 self-heal runner、YAML registry 和部分脚本型能力会退化。

### 基础设施自愈入口

当前仓库还提供 registry-driven 自愈 skill，用于把健康检查、低风险修复、Review Gate 和审计统一起来。

常用诊断命令：

```bash
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py list-items
python3 panopticon/workspaces/nox/skills/self-heal/scripts/self_heal_runner.py diagnose --max-level L1 --exit-zero
```

为其他 agent 生成自愈骨架时，先 dry-run：

```bash
python3 panopticon/global-skills/openclaw-self-heal/scripts/scaffold_agent_self_heal.py --agent metrics --dry-run
```

完整规则见 [infrastructure-self-heal-zh-cn.md](infrastructure-self-heal-zh-cn.md)。

## 8. 发布升级、快路径替换与回滚

这一段同样不是 OpenClaw CLI 子命令，而是当前仓库里升级 Panopticon OpenClaw 运行态的正式入口。

### Prepare

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `python tools/prepare_release_upgrade.py --level full` | 完整 prepare | 会执行 sync、generate、validate、shell 语法检查、Python 编译检查；默认仍可带 smoke |
| `python tools/prepare_release_upgrade.py --level light --skip-smoke` | 轻量 prepare | 会执行 sync、generate、validate、shell 语法检查，适合 fast-panopticon 快路径 |

### Rollout

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `python tools/rollout_release_upgrade.py --mode release` | 发布级 rollout | 默认 `prepare=full`、`verify=smoke`，并包含 Mission Control 服务 |
| `python tools/rollout_release_upgrade.py --mode fast-panopticon` | 快路径替换 8 个 OpenClaw agent | 默认 `prepare=light`、`verify=agent-endpoints`，默认不重建 Mission Control |
| `python tools/rollout_release_upgrade.py --mode fast-panopticon email growth` | 只替换指定 agent | 适合局部验证共享镜像变更 |
| `python tools/rollout_release_upgrade.py --mode fast-panopticon --include-mission-control` | 快路径但同时带上 Mission Control | 用于 agent 与 UI/API 需要一起切换的场景 |
| `python tools/rollout_release_upgrade.py --verify panopticon` | 覆盖默认校验策略 | 也支持 `none`、`agent-endpoints`、`feishu`、`smoke` |
| `python tools/rollout_release_upgrade.py --mode fast-panopticon --verify feishu` | 升级后强制检查飞书状态 | 先跑 endpoint，再检查 Feishu 配置、插件、compiled runtime output、Gateway 加载和 WebSocket 启动 |
| `python panopticon/tools/check_feishu_status.py --tail 800` | 单独检查飞书状态 | 默认不发送飞书消息；真实发送测试需显式使用主动 API 选项 |

当前默认语义：

- `release` 模式保留原来的完整升级链路。
- `fast-panopticon` 模式只聚焦 OpenClaw agent 镜像刷新与容器替换。
- 共享镜像只需 build 一个代表性 `openclaw-*` 服务，但会按选中的 agent 列表 force-recreate 目标容器。

### 2026.4.24 飞书已知升级修复

如果你把 Panopticon agent 升到 OpenClaw `2026.4.24` 后，飞书渠道开始在日志里循环出现下面任一报错：

- `Cannot find package 'openclaw' imported from .../plugin-runtime-deps/.../dist/extensions/feishu/monitor-*.js`
- `failed to load bundled channel setup feishu: Cannot find module '@larksuiteoapi/node-sdk'`

这通常不是飞书凭证问题，而是 stock:feishu 在当前运行布局下有两段依赖解析缺口：

1. runtime monitor 需要从 `plugin-runtime-deps` 解析 `openclaw`
2. global stock Feishu client 需要解析 `@larksuiteoapi/node-sdk`

当前仓库的修复已经落在镜像和启动脚本里，所以运维动作应当是重建目标 agent 容器，而不是只改 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`。

常用修复命令：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build --no-deps openclaw-nox
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build --no-deps openclaw-email openclaw-growth openclaw-health openclaw-metrics openclaw-personal openclaw-trades openclaw-writing
```

生成的 Panopticon compose 会对 `openclaw-*` 构建启用 `cache_from: openclaw-docker-cn-im:local` 和 inline cache。只要本机还保留上一版 `openclaw-docker-cn-im:local` 镜像，即使 builder cache 被清理，也应优先复用 apt、OpenClaw npm 和 Playwright/Chromium 这些重层；首次完整冷构建仍会受 Debian apt 与 npm 网络速度影响。

局部验证时，也可以只替换单个服务：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d --build --no-deps openclaw-email
```

建议至少做两步校验：

```bash
docker logs openclaw-nox --since 3m 2>&1 | grep -E 'feishu|Cannot find package|Cannot find module|channel exited'
docker exec openclaw-nox sh -lc 'test -L /home/node/.openclaw/plugin-runtime-deps/node_modules/openclaw && echo bridge-ok'
```

如果日志不再出现上述缺包报错，再做一次真实飞书收发测试。更完整的飞书排障说明见 [feishu-setup-zh-cn.md](feishu-setup-zh-cn.md)。

### 2026.4.29 飞书 open 策略兼容修复

如果升级到 OpenClaw `2026.4.29` 后，飞书私聊消息能进入日志，但 agent 不处理 / 不回复，并看到：

```text
blocked unauthorized sender ... (dmPolicy=open)
```

通常是因为新版要求 `channels.feishu.dmPolicy="open"` 时必须显式设置：

```json
"allowFrom": ["*"]
```

当前仓库的 `external/OpenClaw-Docker-CN-IM/init.sh` 已在配置合并阶段自动补齐这个字段。运维动作建议是刷新镜像 / 重建目标 agent，而不是只重启进程：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml build openclaw-nox
docker compose -f panopticon/docker-compose.panopticon.yml up -d --no-deps --force-recreate openclaw-nox
```

如需一次性验证所有 agent 的配置和运行状态：

```bash
python3 - <<'PY'
import json
from pathlib import Path
bad = []
for path in sorted(Path('panopticon/agent-homes').glob('*/openclaw.json')):
    cfg = json.load(open(path)).get('channels', {}).get('feishu') or {}
    ok = cfg.get('dmPolicy') != 'open' or '*' in (cfg.get('allowFrom') or [])
    print(path.parent.name, 'ok=' + str(ok), 'dmPolicy=' + repr(cfg.get('dmPolicy')), 'allowFrom=' + repr(cfg.get('allowFrom')))
    if not ok:
        bad.append(path.parent.name)
raise SystemExit(1 if bad else 0)
PY

bash panopticon/tools/check_panopticon_services.sh
```

飞书真实发送验证仍以 `tenant_access_token` 和 `im/v1/messages` 返回 `code=0` 为准。

### Rollback

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `python tools/rollback_release_upgrade.py` | 回滚上一次 rollout | 从 `.release-state/last-rollout.json` 读取 snapshot、mode、verify 等 metadata |
| `python tools/rollback_release_upgrade.py --snapshot .release-state/release-<stamp>.yaml` | 指定快照回滚 | 适合需要显式回退到某次 release contract 时 |
| `python tools/rollback_release_upgrade.py --smoke-base-url http://localhost:18920` | 覆盖回滚后 smoke 地址 | 适合网关地址被临时改动时 |

### 版本门禁与 metadata

rollout 和 rollback 现在都带运行版本硬门禁，不再只看 compose 重建是否成功：

- 如果部分服务版本未变化，会告警并打印 before / after 对照表。
- 如果所有目标服务版本都未变化，脚本直接失败，避免把 no-op 当成成功升级或成功回滚。
- 对比结果除了文本表格，还会写入结构化 rows，方便后续脚本或前端消费。

当前 `.release-state/last-rollout.json` 会记录的关键字段包括：

- `mode`、`prepare_level`、`verify_strategy`
- `build_targets`、`recreate_services`
- `pre_runtime_versions`、`post_runtime_versions`
- `runtime_version_changed_services`、`runtime_version_unchanged_services`
- `runtime_version_gate_passed`
- `runtime_version_comparison_table`
- `runtime_version_comparison_rows`
- `rollback_runtime_version_comparison_table`
- `rollback_runtime_version_comparison_rows`

如果你的目标是“先快速把 Panopticon 的 OpenClaw 容器切到新版本，再决定要不要做完整发布级校验”，优先顺序应当是：

1. `python tools/prepare_release_upgrade.py --level light --skip-smoke`
2. `python tools/rollout_release_upgrade.py --mode fast-panopticon --verify feishu`（未使用飞书时可继续用默认 verify）
3. `python panopticon/tools/check_feishu_status.py --tail 800`
4. 必要时再执行 `python tools/rollback_release_upgrade.py`

## 9. 安全隔离、审批与备份

多 agent 长期运行时，不应把安全能力留到最后补。

| 命令 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `openclaw sandbox ...` | 管理代码执行沙盒 | 适合限制 agent 的执行边界 |
| `openclaw approvals ...` | 管理敏感操作审批 | 适合高危动作的人审闭环 |
| `openclaw security ...` | 做本地安全审计和合规检查 | 适合排查明文密钥暴露 |
| `openclaw backup create` | 创建运行态备份 | 建议在大版本升级前做 |
| `openclaw backup verify` | 校验备份可恢复性 | 备份不是只看是否生成 |

## 10. 全局参数与隔离环境

这些参数可以加在任何命令前后，用来做环境隔离、开发调试与日志控制。

| 参数 | 说明 | 示例 / 备注 |
| --- | --- | --- |
| `--dev` | 开发者隔离环境 | 常见于破坏性测试或新模型验证 |
| `--profile <name>` | 多环境 / 多租户隔离 | `openclaw --profile work gateway` |
| `--container <name>` | 在指定容器内执行 CLI | 适合容器化运维 |
| `--log-level <level>` | 控制日志级别 | `trace / debug / info / warn / error / fatal / silent` |

高阶建议：

如果你想在不污染主线记忆、配置和渠道状态的前提下测试新模型或新技能，优先使用 `--dev` 或独立 `--profile`，不要直接在主工作区硬改。

## 11. 重置与卸载

当配置已严重漂移，最好的办法不是继续补丁，而是明确区分“软重置”和“硬重置”。

| 命令 | 说明 | 备注 |
| --- | --- | --- |
| `openclaw reset` | 软重置，本体保留 | 清空本地配置和状态 |
| `openclaw uninstall` | 硬重置，数据删除 | 通常会停止服务并删除运行态数据 |

执行前建议先做：

1. `openclaw backup create`
2. 导出当前关键配置
3. 记录现有模型、渠道和插件状态

## 12. 面向系统迭代的最小命令集

如果你的目标不是“把 CLI 全学会”，而是支持本仓库持续迭代，先记住下面这组最小闭环：

```bash
openclaw models status
openclaw health
openclaw gateway status
openclaw logs --follow
openclaw config validate
openclaw doctor --fix
openclaw models list
openclaw dashboard --no-open
```

这组命令覆盖了：

- 模型是否可用
- gateway 是否在线
- 配置是否合法
- 日志是否有明显异常
- dashboard 是否能打开

对多 agent 主路线，再补一组：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml ps
docker compose -f panopticon/docker-compose.panopticon.yml logs -f --tail=200
bash panopticon/tools/check_panopticon_services.sh
python tools/rollout_release_upgrade.py --mode fast-panopticon
```

## 13. 版本对齐与资料可信度说明

为了避免“搜到一篇旧教程，结果命令和字段都变了”的问题，本仓库对 CLI 文档采用以下可信度分层：

1. 第一优先级：当前仓库可运行脚本、compose、env 模板、[../openclaw-release.yaml](../openclaw-release.yaml)
2. 第二优先级：当前仓库 README 与 docs 中已出现并被实际使用的命令
3. 第三优先级：OpenClaw 2026.4.29 外部参考资料与 `openclaw --help`

如果三者冲突，按第一优先级回退。

## 14. 一页 TL;DR

- 首次安装：`openclaw setup`、`openclaw configure`
- 配置修复：`openclaw config validate`、`openclaw doctor --fix`
- 模型检查：`openclaw models status`、`openclaw models list`
- gateway 运维：`openclaw gateway start`、`openclaw gateway status`、`openclaw gateway restart`
- 日志与健康：`openclaw logs --follow`、`openclaw health`
- 控制台入口：`openclaw dashboard --no-open`
- 升级与回滚：`python tools/rollout_release_upgrade.py --mode fast-panopticon`、`python tools/rollback_release_upgrade.py`
- 多 agent 主路线：额外依赖 [../panopticon/README.md](../panopticon/README.md) 中的 compose 与巡检脚本

如果你只保留一个判断标准，就记这一句：CLI 用来操作，仓库脚本用来编排，版本以 [../openclaw-release.yaml](../openclaw-release.yaml) 为准。