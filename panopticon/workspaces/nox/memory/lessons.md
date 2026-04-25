# lessons.md (nox)

## Reusable Lessons

### Roadmap & Planning
- 路线建议必须给出证据与取舍说明
- 优先暴露阻塞项与下一步可执行动作
- 多方案对比时，提供明确决策指南（如果...则...）
- 长期等待决策的项目应标记为"挂起"，避免误认为阻塞

### Task Management
- 任务完成后如等待外部决策，应明确标记"等待用户决策"
- 提供可追溯的输出结构：`artifacts/<task_id>/` + `sources/<task_id>/`
- 定期检查旧任务的时效性，超过一周未响应的可归档
- 长期挂起项目的清理策略：超过 10 天等待用户决策的任务应标记归档建议
- 项目状态应定期同步到 `projects.md`，避免信息过时

### Heartbeat Operations
- I/O-only heartbeat 稳定运行，无需额外推测任务
- 每日脉冲保持一致结构（风险/阻塞/依赖/Review 需求）
- 状态文件（heartbeat-state.json）有效追踪检查间隔
- Weekly Review 机制化：每周总结 lessons 并更新长期索引

### 容器环境恢复 (2026-04-11)
- **问题**：容器重建后 pip、bypy、python-pptx 等包全部丢失
- **修复路径**：
  1. 安装 pip：`python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/home/node/get-pip.py')"` → `python3 /home/node/get-pip.py --user --break-system-packages`
  2. 加 PATH：`export PATH="$HOME/.local/bin:$PATH"`
  3. 从 U 盘批量装包：`BREAK_SYSTEM_PACKAGES=1 /mnt/usb/package3.11/autoinstall-linux.sh`
- **bypy 授权**：容器重建后 token 丢失，需重新授权。快速方式：手动调百度 OAuth API 换 token 写入 `/home/node/.bypy/bypy.json`
- **注意事项**：python-pptx 0.6.21 与 Python 3.11 不兼容（collections.abc 问题），需升级到 0.6.23+
- **关键文件**：离线包在 `/mnt/usb/package3.11/linux-package311/`，198 个 whl

### Tooling & Skills (Week of 3/2-3/6)
- Progressive Disclosure 架构显著节省上下文：McKinsey Consultant Skill 按 8 步工作流逐步加载，避免一次性加载所有参考文档
- 跨对话续写需要状态标注：页面依赖关系 (page-dependencies.md) 是关键
- 外部数据依赖应提前确认：AI 玩具市场分析因缺少 web_search API key 被阻塞，应在项目启动前明确工具可用性

### 费用追踪与结算 (Week of 3/6-3/9)
- 费用追踪需要清晰的分类逻辑：团建费用（目标金额）vs 其他支出
- 平摊计算需要明确参与名单和计算规则（员工平摊 vs 其他支出）
- 最终结算需要人工确认后再落盘，避免计算错误

### 运营模式 (Week of 3/10-3/11)
- 阻塞项需要明确的恢复路径和依赖清单
- 项目生命周期管理：Active → Completed/Blocked/Pending → 归档
- 外部工具依赖检查应在项目启动前置，而非阻塞后才发现

### 模型配置与图像识别 (2026-04-13)
- **问题**：OpenClaw 图像识别失败，报 `Unknown model` 错误

### 插件安装与依赖管理 (Week of 2026-04-18)
- **Rokid 插件安装**：
  - 容器网络问题导致 npm install 超时，改用符号链接复用主应用 node_modules
  - 解决方案：`ln -s /usr/local/lib/node_modules/openclaw/node_modules/ws node_modules/ws`
  - 关键点：插件依赖可通过符号链接复用主应用模块，避免重复安装
- **配置验证**：插件配置需正确设置 linkCode 和 linkSecret，Gateway 重启后生效
- **DeepSeek 模型集成**：
  - 成功添加 DeepSeek provider 到 OpenClaw 配置
  - 费用结构：输入（缓存命中）0.2元/百万tokens，输入（缓存未命中）2元/百万tokens，输出3元/百万tokens
  - 模型回退链配置：default/glm-5-turbo → deepseek/deepseek-chat → default/glm-4.7
  - 关键点：多模型回退链提高服务稳定性，成本透明化
- **根因**：
  1. 视觉模型 `glm-4v-flash` 在智谱 AI API 中不存在，正确名称为 `glm-4v`
  2. 主对话模型 `glm-4.7`、`glm-5-turbo` 被错误标注为支持 image 输入，导致含图片消息直接走主模型失败
  3. codex 提供商配置不完整（缺少 baseUrl/models），导致整体配置验证报错
- **修复**：
  1. `imageModel.primary`：`glm-4v-flash` → `glm-4v`
  2. 主对话模型 `glm-4.7`、`glm-5-turbo`、`gpt-4o` 的 input 改为仅 `text`
  3. 补全 codex 提供商的完整配置
- **涉及配置文件**：`~/.openclaw/openclaw.json`（主配置）+ `~/.openclaw/agents/main/agent/models.json`（agent 级配置，实际以 openclaw.json 为准）
- **关键教训**：
  - 两个配置文件同时存在时，`openclaw.json` 是主配置，优先修改此文件
  - 模型能力声明（input 字段）必须与 API 实际能力匹配，否则会导致含图片消息处理失败
  - 修改模型配置后，图像工具使用新的 `imageModel` 配置，无需重启即可生效