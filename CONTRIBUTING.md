# 贡献指南

欢迎提交文档优化、脚本修复、Panopticon 模板改进、Mission Control 功能增强和回归测试补充。

这个仓库最需要的贡献，不是“再加一层复杂度”，而是让新用户更快跑通主路线，让维护者更容易确认行为边界。

## 贡献前先读

1. [README.md](README.md)
2. [panopticon/README.md](panopticon/README.md)
3. [docs/README.md](docs/README.md)

如果你的改动涉及 Mission Control API 或知识系统，再补读：

1. [mission_control_api/README.md](mission_control_api/README.md)
2. [docs/knowledge-system-playbook-zh-cn.md](docs/knowledge-system-playbook-zh-cn.md)

## 欢迎哪些贡献

- 缩短安装和排障路径的文档改进
- 修复 manifest、env 模板、生成器和校验器的不一致
- 补充回归脚本或把手工排查动作沉淀成脚本
- 改进 Mission Control UI / API 的可用性和可观测性
- 提高知识系统导入、治理、resolve 或 rollback 的稳定性

## 不建议的改动方式

- 不要直接长期维护生成产物，优先改 manifest 或生成器。
- 不要把本地 `.env`、token、数据库快照或运行态工作区提交进仓库。
- 不要把实验性路径写成默认推荐路径。
- 不要在运行时补 DDL 来绕过 Alembic 迁移。

## 本地检查

提交前，至少跑与你改动相关的最小检查。

### 通用最小检查

```bash
python -m pip install -r panopticon/tools/requirements.txt
python panopticon/tools/validate_panopticon.py
python panopticon/tools/validate_skills_template.py
python -m compileall mission_control_api/app mission_control_api/alembic panopticon/tools tools
```

### Mission Control UI

在已安装 [MissionControl/requirements.txt](MissionControl/requirements.txt) 依赖的环境中运行：

```bash
python3 -m unittest discover -s MissionControl/tests -p 'test_ui_callbacks.py' -v
node --check MissionControl/assets/task_detail.js
```

回调测试模拟业务 API 和 WebSocket 线程，不会创建任务、提交评论或操作 Agent。
详情草稿按任务保存在当前页面内存中，刷新页面不会保留；提交期间表单暂时禁用，这不等同于服务端幂等保证。

浏览器回归至少检查：任务卡 Enter/Space、弹窗 Esc 和焦点返回、A/B 任务草稿隔离、阈值输入等待两个刷新周期不被覆盖，以及预览后修改字段不沿用旧自动负责人。
在桌面和手机短屏检查弹窗、长标题及语音状态文字；用服务端 API 日志或调用计数验证搜索和筛选的请求量，浏览器 Network 只能直接观察 Dash 回调。

局域网性能回归还应检查 gzip 协商、版本指纹脚本的缓存命中，以及页面、布局和回调继续使用 `no-store`。
定时刷新请求不应携带看板和 Feed 快照；完整快照只在切换筛选时回传。
模拟没有业务事件的 WS 连接，验证首屏仍能加载、60 秒安全校准仍会执行，首次读取失败后在五秒间隔重试。
桌面 1280px 和 1440px 应完整显示五列；手机使用纵向状态分组，页面不能横向溢出。

### 生成产物一致性

```bash
python panopticon/tools/generate_panopticon.py --prune
git diff --exit-code -- panopticon/docker-compose.panopticon.yml panopticon/env/*.env.example
```

### Compose 渲染检查

```bash
for example in panopticon/env/*.env.example; do
  target="${example%.example}"
  if [ ! -f "$target" ]; then
    cp "$example" "$target"
  fi
done

docker compose -f panopticon/docker-compose.panopticon.yml config >/tmp/panopticon.compose.rendered.yml
```

如果你改的是知识系统，再额外运行相应脚本，例如：

- [tools/verify_knowledge_p0_regression.sh](tools/verify_knowledge_p0_regression.sh)
- [tools/verify_knowledge_ocr_flow.sh](tools/verify_knowledge_ocr_flow.sh)
- [tools/verify_knowledge_dynamic_policy_rollout_flow.sh](tools/verify_knowledge_dynamic_policy_rollout_flow.sh)

## 文档改动标准

- 先回答“用户下一步要做什么”，再展开背景。
- 把默认路径、推荐路径和实验路径明确分开。
- 能用一条命令说明的，不要写成一整段概念介绍。
- 解释高风险能力时，必须同时写清边界和不推荐场景。
- 文件间避免重复复制大段内容，根 README 负责选路，专题文档负责细节。

## PR 说明建议

PR 描述至少包含：

- 改了什么
- 为什么要改
- 影响哪条路径：单 Agent / Panopticon / Mission Control / Knowledge
- 跑了哪些验证
- 是否涉及破坏性变更或迁移

## 安全问题

如果你发现的是凭证泄露、权限绕过、远程执行边界或数据暴露问题，不要直接公开贴出可复现敏感细节。先用仓库的安全渠道或维护者私下沟通。
