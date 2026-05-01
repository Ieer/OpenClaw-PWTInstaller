# OpenClaw Panopticon 备份、迁移与保留策略

本文面向当前仓库主路线：`8-Agent Panopticon + Mission Control`。它不是单一 `~/.openclaw` 目录备份方案，而是覆盖 Agent homes、workspaces、Mission Control PostgreSQL/Redis、env 覆盖文件、知识源与容器编排指纹的分层备份策略。

## 核心原则

1. **日常不停机增量备份降低 RPO，但不替代迁移级冷备。**
2. **PostgreSQL 禁止在线物理拷贝。** 日常备份使用 `pg_dump -Fc`，恢复使用 `pg_restore`。
3. **Redis 视作可选恢复项。** AOF/BGSAVE 可保存，但事实源以 PostgreSQL 与文件层为准。
4. **U 盘不散装保存 Linux 数据目录。** U 盘只保存 restic repo 与 `tar.gz`/`tar.zst` 备份包，避免 FAT32/exFAT 丢失权限、owner 与 symlink。
5. **升级前后必须做基线。** Mission Control API 启动时会自动执行 Alembic schema migration，升级后的数据库不应直接交给旧版本服务。

## 备份类型

| 类型 | 是否停机 | 推荐频率 | 目标 | 推荐命令 |
| --- | --- | --- | --- | --- |
| 日常增量 | 不停机 | 每天；重要数据每 1-6 小时 | 防误删、短周期回滚 | `daily-incremental` |
| 近零停顿快照 | 几秒 pause（后续增强） | 每天低峰 | 提高文件层一致性 | 先用日常增量替代 |
| 周全量冷备 | 短暂停机 | 每周 | 主恢复点 | `weekly-full --yes --restart-after` |
| 月迁移级全量 | 短暂停机 | 每月 | 换机、系统重装、U 盘迁移 | `weekly-full --yes --restart-after` 并长期保留 |
| 升级前基线 | 短暂停机 | 每次升级前 | 防 Alembic 不可逆升级 | `weekly-full --yes --restart-after` |
| 升级后基线 | 短暂停机 | 每次升级后 | 新版本恢复基线 | `weekly-full --yes --restart-after` |

## 工具入口

备份工具位于：

```bash
python panopticon/tools/backup_panopticon.py --help
```

先查看当前数据边界：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  plan
```

## 日常不停机增量备份

日常增量默认使用 `restic`，需要先设置加密密码或密码文件：

```bash
export RESTIC_PASSWORD='replace-with-a-strong-password'
```

首次初始化并运行：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  daily-incremental \
  --init-restic \
  --restic-check
```

之后日常运行：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  daily-incremental \
  --restic-check
```

日常增量做三件事：

1. 在线导出 PostgreSQL：`pg_dump -Fc`。
2. 触发 Redis `BGSAVE`（失败只告警）。
3. 用 restic 对核心文件目录做加密去重快照。

默认纳入的文件层包括：

- `agent-homes/`
- `workspaces/`
- `env/`
- `.env`
- `agents.manifest.yaml`
- `global-skills/`
- `templates/`
- `reports/`
- `PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH` 指向的知识源目录（存在时）

默认排除：浏览器锁文件、socket、pid/lock、缓存、临时目录、`node_modules/`、`extensions/`。

## 周期全量冷备

全量包会包含 env 文件、API Key、Gateway Token、渠道登录状态、Agent 会话和浏览器状态。请把它写入加密 U 盘、加密移动硬盘，或再放入受控的加密备份仓库；不要把 `payload.tar.gz` 上传到不可信云盘。

迁移级全量备份需要允许短暂停机：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  weekly-full \
  --yes \
  --restart-after
```

流程：

1. 先在线导出 PostgreSQL 逻辑 dump。
2. 触发 Redis 快照。
3. `docker compose down` 停止 Panopticon。
4. 创建 `payload.tar.gz`，保存 POSIX 权限、owner、symlink 与备份元数据。
5. 写入 `manifest.json` 与 `checksums.sha256`。
6. 如指定 `--restart-after`，自动恢复服务。

如只想做演练、不停服务，可使用：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  weekly-full \
  --no-stop
```

`--no-stop` 只能视为 warm full，不建议作为换机迁移的权威备份。

## 校验

校验全量备份集：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  verify \
  --backup-set /media/pi/YOUR_USB/openclaw-backups/runs/<run-id>
```

同时校验 restic repo：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  verify \
  --backup-set /media/pi/YOUR_USB/openclaw-backups/runs/<run-id> \
  --restic-check
```

## 保留与清理

推荐保留策略：

- 日常增量：30 天。
- 周快照：8 份。
- 月快照：12 份。

执行 restic prune：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  prune \
  --keep-daily 30 \
  --keep-weekly 8 \
  --keep-monthly 12
```

## systemd user timer

定时器建议使用 `RESTIC_PASSWORD_FILE`，不要把 `RESTIC_PASSWORD` 明文写进 systemd unit。示例：

```bash
mkdir -p ~/.config/openclaw-backup
printf '%s\n' 'replace-with-a-strong-password' > ~/.config/openclaw-backup/restic-password
chmod 600 ~/.config/openclaw-backup/restic-password
export RESTIC_PASSWORD_FILE=$HOME/.config/openclaw-backup/restic-password
```

生成 systemd user timer 模板：

```bash
python panopticon/tools/backup_panopticon.py \
  --backup-root /media/pi/YOUR_USB/openclaw-backups \
  install-timers
```

启用：

```bash
systemctl --user daemon-reload
systemctl --user enable --now \
  openclaw-panopticon-backup-daily.timer \
  openclaw-panopticon-backup-weekly.timer
```

如果机器没有启用用户 lingering，重启后 user timer 可能不会运行；可按系统策略启用 lingering，或后续改成 system-level timer。

## 恢复与演练建议

恢复流程分三层：

1. **单文件恢复**：从 restic snapshot 恢复到临时目录，人工确认后覆盖。
2. **日常增量恢复**：恢复最新 restic snapshot + 最新 PostgreSQL dump。
3. **灾难恢复/换机迁移**：使用最新冷态全量包，导入 PostgreSQL dump，修复权限，重新生成 Compose，再运行健康检查。

恢复后至少执行：

```bash
python panopticon/tools/generate_panopticon.py --prune
bash panopticon/tools/check_panopticon_services.sh
python panopticon/tools/test_workspace_contract.py
```

如涉及 Mission Control 或多 Agent 工作流，建议再执行综合评估：

```bash
python panopticon/tools/comprehensive_assessment.py
```

## 升级/容器重构前的强制步骤

每次执行 OpenClaw 大版本升级、Mission Control schema 变更、容器拆分或挂载重构前：

1. 运行一次 `weekly-full --yes --restart-after`。
2. 校验 `checksums.sha256`。
3. 确认 `manifest.json` 中版本、compose hash、agents manifest hash 已记录。
4. 升级后再生成一份新的 full baseline。

不要把已经被新版 Alembic 升级过的 PostgreSQL 物理目录直接交给旧版本服务。需要回退时，应使用升级前的 full baseline。