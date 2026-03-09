# Workspace Skeleton（可复制骨架包）

把本目录复制到 `panopticon/workspaces/<agent>/` 后，替换占位符即可直接使用。

占位符：

- `{{AGENT_SLUG}}`：agent 标识（如 `email`）
- `{{IDENTITY_NAME}}` / `{{IDENTITY_CREATURE}}` / `{{IDENTITY_VIBE}}` / `{{IDENTITY_EMOJI}}` / `{{IDENTITY_AVATAR}}`
- `{{TODAY}}`：日期（YYYY-MM-DD）

建议：优先使用脚本生成，避免手工漏改。

- `python panopticon/tools/scaffold_workspace_docs.py --agent <slug>`
- 若运行态目录在仓库外，可设置：
	- `PANOPTICON_WORKSPACES_ROOT=/your/data/workspaces`
	- 或 `PANOPTICON_DATA_DIR=/your/data`（脚本自动使用其下 `workspaces/`）
