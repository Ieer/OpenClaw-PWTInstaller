# writing workspace 运行态边界

本 workspace 采用“源码可版本化、运行态本地化”策略。

## 可版本化（建议保留在仓库）

- 角色与协作文档：`AGENTS.md`、`SOUL.md`、`USER.md`、`IDENTITY.md`、`HEARTBEAT.md`、`TOOLS.md`、`MEMORY.md`
- 能力与实现源码：`skills/`、`components/`、`core/`、`*.js`、`*.py`、`package.json`
- 团队长期知识：`memory/projects.md`、`memory/infra.md`、`memory/lessons.md`

## 本地化（不入库）

- 运行契约目录：`inbox/`、`outbox/`、`artifacts/`、`state/`、`sources/`
- 运行状态与缓存：`.openclaw/`、`node_modules/`
- 日志型记忆：`memory/YYYY-MM-DD.md`、`memory/heartbeat-state.json`
- 生成产物：`*.pptx`、`thumbnails/`、临时测试输出

## 路径建议

- 统一使用 `PANOPTICON_DATA_DIR`（或显式 `PANOPTICON_WORKSPACES_ROOT`）承载本地运行态目录。
- 仓库内 `panopticon/workspaces/writing/` 作为基线与源码容器，不作为长期运行态落盘目录。
