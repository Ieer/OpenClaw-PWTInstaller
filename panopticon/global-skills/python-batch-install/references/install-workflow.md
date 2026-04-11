# 安装与排障流程

## 标准安装流程

1. 识别目标解释器。

- 默认使用 `/usr/bin/python3` 创建虚拟环境。
- 安装和验证时必须使用目标 venv 的 Python。

2. 创建虚拟环境。

- 默认目录是 `/home/pi/.venvs/<env-name>`。
- 不要把 venv 创建在 exFAT、FAT 或不支持符号链接的挂载目录里。
- Windows 场景优先使用 `py -3.11 -m venv` 或明确的 `python.exe -m venv`。

2.5. 准备环境清单。

- 复制 `assets/environment-manifest.template.yaml` 为本次任务配置文件。
- 如果只是想快速参考当前仓库的已验证写法，可直接查看 `assets/environment-manifest.example.yaml`。
- 在配置中填写 Linux 或 Windows 的环境名、解释器、requirements 和 wheel 仓库。
- Linux 和 Windows helper 共用 `scripts/manifest_common.py` 中的 manifest 解析逻辑，避免两边各自维护一份 YAML 解析实现。
- Linux 批量脚本默认读取这份配置，也支持通过 `MANIFEST_FILE=/path/to/manifest.yaml` 指定其他清单。
- Linux 侧的 manifest 解析由 `scripts/render_linux_manifest_env.py` 负责，shell 脚本只消费 helper 输出的环境变量。
- Windows 批量脚本默认读取这份配置，也支持通过 `MANIFEST_FILE=C:\path\to\manifest.yaml` 指定其他清单。
- Windows 侧的 manifest 解析由 `scripts/render_windows_manifest_env.py` 负责，批处理文件只消费 helper 输出的环境变量。
- 两边脚本都支持 `DRY_RUN=1` 只打印计划，不执行 venv 创建、pip 安装或验证命令。
- 批量脚本应优先读取这份配置，而不是手改脚本正文。

3. 执行离线安装。

- 默认调用 `/media/pi/4A21-0000/package3.11/autoinstall-linux.sh`。
- 默认 requirements 使用 `/media/pi/4A21-0000/package3.11/package-linux-arm64.txt`。
- 默认 wheel 仓库使用 `/media/pi/4A21-0000/package3.11/linux-package311`。
- Windows 批量脚本默认在目标 venv 内直接执行与 `autoinstall-win.bat` 等价的非交互步骤，requirements 使用 `package-windows-x64.txt`，wheel 仓库使用 `windows-package311`。
- 如果需要人工排障或手工恢复，仍可以单独运行 `autoinstall-win.bat`。

4. 执行最小验证。

- `python -m pip show python-pptx lxml Pillow`
- `python -c "from pptx import Presentation; print(type(Presentation()).__name__)"`
- Windows 可用 `python -c "from pptx import Presentation; print(type(Presentation()).__name__)"` 做同样验证。

5. 汇总成功和失败项。

- 记录环境名。
- 记录解释器路径。
- 记录安装结果。
- 记录导入验证结果。

## 已知风险点

- 使用系统 Python 可能触发 PEP 668。
- 将 Linux 安装误指向 Windows wheel 仓库会直接失败。
- 将 Windows 安装误指向 Linux wheel 仓库同样会失败。
- 某些重型二进制依赖必须有 arm64 和 cp311 对应 wheel。
- `playwright` 的 Python 包安装成功，不代表浏览器二进制已经就绪。

## 常见故障处理

### requirements 文件不存在

- 检查 `REQ_FILE` 是否仍指向 `package-linux-arm64.txt`。
- 检查工作区挂载路径是否变化。

### wheel 仓库错误

- 检查 `PACKAGE_DIR` 是否是 `linux-package311`。
- 避免把 Linux 安装指向 `windows-package311`。
- Windows 任务要反向检查，避免把安装指向 `linux-package311`。

### 导入失败

- 先执行 `pip show`，确认包装在目标 venv 中。
- 再执行最小导入命令，确认不是解释器混用。
- 对单包失败做单独复现，不要整批重装后再猜测原因。

### Python 3.11 兼容问题

- 优先检查历史包是否直接引用 `collections` 旧接口。
- 当前仓库中的 `python-pptx 0.6.21` Linux wheel 已修补，可直接验证导入。