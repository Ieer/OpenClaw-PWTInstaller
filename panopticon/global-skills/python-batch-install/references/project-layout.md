# 项目路径与默认值

这个技能基于当前工作区的真实文件结构，而不是泛化的容器示例路径。

## 已确认路径

- 工作区根目录：`/media/pi/4A21-0000/package3.11`
- Linux 离线 wheel 仓库：`/media/pi/4A21-0000/package3.11/linux-package311`
- Windows 离线 wheel 仓库：`/media/pi/4A21-0000/package3.11/windows-package311`
- Linux requirements 文件：`/media/pi/4A21-0000/package3.11/package-linux-arm64.txt`
- Windows requirements 文件：`/media/pi/4A21-0000/package3.11/package-windows-x64.txt`
- Linux 离线安装脚本：`/media/pi/4A21-0000/package3.11/autoinstall-linux.sh`
- Windows 离线安装脚本：`/media/pi/4A21-0000/package3.11/autoinstall-win.bat`
- 推荐 venv 根目录：`/home/pi/.venvs`

## 当前真实环境

- 已验证可用的环境名：`package3.11`
- 已验证解释器路径：`/home/pi/.venvs/package3.11/bin/python`

## 技能资源

- Linux 批量安装脚本模板：`panopticon/global-skills/python-batch-install/scripts/batch-install-linux.sh`
- 共享 manifest 解析模块：`panopticon/global-skills/python-batch-install/scripts/manifest_common.py`
- Linux manifest helper：`panopticon/global-skills/python-batch-install/scripts/render_linux_manifest_env.py`
- Windows 批量安装脚本模板：`panopticon/global-skills/python-batch-install/scripts/batch-install-windows.bat`
- Windows manifest helper：`panopticon/global-skills/python-batch-install/scripts/render_windows_manifest_env.py`
- 环境清单模板：`panopticon/global-skills/python-batch-install/assets/environment-manifest.template.yaml`
- 环境清单示例：`panopticon/global-skills/python-batch-install/assets/environment-manifest.example.yaml`

## 关于 OpenClaw 容器结构

当前仓库本身包含 Dockerfile 和 compose 文件，例如根目录下的 `Dockerfile`、`docker-compose.yml`，以及 `panopticon/docker-compose.panopticon.yml`。但这些文件并不描述 `/media/pi/4A21-0000/package3.11` 这套离线包目录的挂载结构，所以这个技能的默认安装路径仍以当前已验证的外部安装树为准：

- 代码和离线包位于 `/media/pi/4A21-0000/package3.11`
- 虚拟环境位于 `/home/pi/.venvs`
- Linux 安装入口是 `autoinstall-linux.sh`
- Windows 手工安装入口是 `autoinstall-win.bat`；技能里的 `batch-install-windows.bat` 则执行等价的非交互流程，便于批量自动化。

如果后续仓库中补充了容器编排文件，应优先按容器挂载路径重写这些默认值。

## 当前仓库中的 Python 3.11 兼容说明

- `linux-package311/python_pptx-0.6.21-py3-none-any.whl` 已经修补 `collections.abc` 导入问题。
- 离线安装后已验证 `from pptx import Presentation` 可以在 Python 3.11 中成功执行。