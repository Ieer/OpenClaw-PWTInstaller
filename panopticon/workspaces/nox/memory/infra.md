# infra.md (nox)

## Python 环境

- **Python**: 3.11 (`/usr/bin/python3`), Debian 系, 无 sudo
- **pip**: 用户级安装 (`/home/node/.local/bin/pip3`), 需手动加 PATH
- **离线包**: `/mnt/usb/package3.11/linux-package311/` (198 whl, arm64)
- **一键恢复**: `BREAK_SYSTEM_PACKAGES=1 /mnt/usb/package3.11/autoinstall-linux.sh`
- **pip 安装**: `python3 /home/node/get-pip.py --user --break-system-packages`
- **bypy**: 需授权, token 写入 `/home/node/.bypy/bypy.json`
- **已知不兼容**: python-pptx 0.6.21 + Python 3.11 = collections.abc 报错

## Integrations

- 产品/工程数据源与任务协作系统（按实际接入维护）

## Guardrails

- 不记录密钥/token 明文
- 任何外部承诺动作必须先 Review

## Heartbeat 配置

- **当前偏好**：每天一次，静默时段 北京时间 18:00–23:00（UTC 10:00–15:00）（用户确认于 2026-03-10）
- **实施方式**：OpenClaw cron 调度配置
- **任务配置**：
  - 频率：每天一次（建议 UTC 16:00，避开静默时段）
  - 静默时段：UTC 10:00–15:00（北京时间 18:00–23:00）