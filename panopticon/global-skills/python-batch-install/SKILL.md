---
name: python-batch-install
description: '在 OpenClaw 重构或重建容器后，批量创建和安装 Python 环境。用于离线 wheel 仓库安装、venv 批量初始化、requirements 分组安装、Python 3.11 兼容修复验证、失败重试与安装结果汇总。适用于 Debian、Ubuntu、容器镜像和树莓派 arm64 场景。'
argument-hint: '提供容器类型、Python 版本、环境列表、requirements 文件、wheel 目录和是否离线安装'
user-invocable: true
disable-model-invocation: false
---

# Python Batch Install

## When to Use

- OpenClaw 容器重构后，需要批量重建 Python 虚拟环境。
- 需要从当前仓库的离线 wheel 仓库安装依赖。
- 需要统一执行安装、导入验证和失败汇总。

## 当前项目默认值

这个技能已经按当前工作区的真实结构预设：

- 工作区根目录：`/media/pi/4A21-0000/package3.11`
- Linux wheel 仓库：`/media/pi/4A21-0000/package3.11/linux-package311`
- Windows wheel 仓库：`/media/pi/4A21-0000/package3.11/windows-package311`
- Linux requirements：`/media/pi/4A21-0000/package3.11/package-linux-arm64.txt`
- Windows requirements：`/media/pi/4A21-0000/package3.11/package-windows-x64.txt`
- 离线安装脚本：`/media/pi/4A21-0000/package3.11/autoinstall-linux.sh`
- Windows 安装脚本：`/media/pi/4A21-0000/package3.11/autoinstall-win.bat`
- venv 根目录：`/home/pi/.venvs`
- 当前已验证环境名：`package3.11`

## Quick Start

1. 先确认当前容器或主机里存在 `/usr/bin/python3`。
2. 新任务从 `assets/environment-manifest.template.yaml` 复制清单；需要快速上手时可直接参考 `assets/environment-manifest.example.yaml`。
3. Linux 批量安装时运行 `scripts/batch-install-linux.sh`，它会默认读取 `assets/environment-manifest.template.yaml`，也可以通过 `MANIFEST_FILE=/path/to/manifest.yaml` 指定其他清单。
4. Windows 批量安装时运行 `scripts/batch-install-windows.bat`，它会默认读取 `assets/environment-manifest.template.yaml`，并在目标 venv 内执行与 `autoinstall-win.bat` 等价的非交互安装和校验流程；也可以通过 `MANIFEST_FILE=C:\path\to\manifest.yaml` 指定其他清单。
5. 遇到异常时查阅 `references/project-layout.md` 和 `references/install-workflow.md`。

需要先预览计划而不执行安装时：

- Linux: `DRY_RUN=1 scripts/batch-install-linux.sh`
- Windows: `set DRY_RUN=1 && scripts\batch-install-windows.bat`

## Execution Rules

- 优先使用 venv，不直接安装到系统 Python。
- 离线安装必须使用 `--no-index --find-links` 或现有安装脚本。
- 安装完成后必须做 `pip show` 和最小导入验证。
- 对 Python 3.11 历史兼容问题做显式检查，特别是 `python-pptx`。
- 批量任务优先通过环境清单配置文件驱动，而不是把环境名硬编码到命令里。

## Deliverables

- 每个目标环境都有明确的成功或失败状态。
- 输出 Python 路径、关键依赖版本和验证结果。
- 失败项有明确错误归因，不接受仅报告“安装失败”。