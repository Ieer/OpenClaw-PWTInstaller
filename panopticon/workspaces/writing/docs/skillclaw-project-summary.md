# SkillClaw 项目完整归档

> 归档日期：2026-05-18
> 来源：GitHub README + arXiv 论文 + 微信公众号文章（作者"李叔"）
> 本地位置：U盘 `/mnt/usb/skills/SkillClaw/`

---

## 一、项目概要

| 字段 | 值 |
|---|---|
| 项目名 | SkillClaw |
| 团队 | AMAP-ML（高德地图） |
| 协议 | MIT 开源 |
| 论文 | arXiv:2604.08377 |
| 发布时间 | 2026-04-10（开源） |
| 仓库 | github.com/AMAP-ML/SkillClaw |
| 论文荣誉 | Hugging Face Daily Papers **第 2 名** |

**一句话定位**：让 AI Agent 的技能从每一次真实交互中自动进化——跨会话、跨 Agent、跨设备、跨用户，经验持续累积，技能群体进化。

---

## 二、核心架构

系统由两个解耦组件构成，通过共享存储通信：

### 2.1 Client Proxy（客户端，必需）
- 本地 API 代理，部署在用户侧
- 拦截 Agent → LLM 的请求（`/v1/chat/completions`, `/v1/messages`）
- 做三件事：记录完整会话轨迹、管理本地 skill 库、上传会话数据到共享存储

### 2.2 Evolve Server（服务端，可选）
- 从共享存储读取会话数据
- 分析成功/失败模式，演化或创建新 skill
- 支持两种 engine：
  - `workflow`：固定三阶段 LLM 流程（Summarize → Aggregate → Execute）
  - `agent`：基于 OpenClaw 的自主 agent 工作区，直接编辑 SKILL.md

### 2.3 共享存储
- 支持：本地文件系统 / Alibaba OSS / AWS S3
- **Client 和 Server 不直接通信**，仅通过存储层耦合

---

## 三、工作原理（6 步流程）

```
用户对话 → Client Proxy 拦截记录 → 上传共享存储
→ Evolve Server 夜间演化 → 验证新技能 → 同步所有用户
```

关键特性：
1. **集体进化**：个体经验 → 共享技能生态
2. **全自动**：无需人工干预
3. **智能体演化**：技能更新通过开放式推理产生，非预定义规则
4. **单调递增**：新技能必须通过验证才会部署，不会越改越差

---

## 四、Benchmark 实验数据（WildClawBench）

6 天连续测试，模拟 **8 个用户并发使用**：

| 任务类型 | 初始 | 6 天后 | 相对提升 |
|---|---|---|---|
| 社交交互类 | 54.01% | 60.34% | +11.72% |
| 搜索与检索类 | 22.73% | 34.55% | **+52.00%** |
| 创意合成类 | 11.57% | 21.80% | **+88.41%** |
| 安全与对齐类 | 24.00% | 32.00% | +33.33% |

> 创意合成和搜索检索类提升最大，说明技能进化在**模式可复现的任务**上效果最显著。

---

## 五、生态兼容

| 框架 | 支持状态 | 备注 |
|---|---|---|
| **OpenClaw** | ✅ 原生 | Server `agent` 引擎基于 OpenClaw |
| **Hermes** | ✅ 深度集成 | `skillclaw setup` 自动改写配置，含 `doctor` / `restore` 命令 |
| **QwenPaw** | ✅ | 2026-04-17 新增 |
| **IronClaw / PicoClaw / ZeroClaw** | ✅ | 完整 Claw 生态支持 |
| **NanoClaw / NemoClaw** | ✅ | 扩展兼容 |
| **OpenAI Codex** | ✅ | 2026-04-20 新增，含 `doctor` / `restore` |
| **Claude Code** | ✅ | 同上，自动接入代理、原生 skills 目录 |
| 任意 OpenAI 兼容 API | ✅ | 基础兼容 |

---

## 六、与现有方案对比

| 方案 | 做法 | 局限 |
|---|---|---|
| 记忆类 | 存储历史会话供检索 | 与场景绑定太紧，难以泛化 |
| 技能类 | 压缩经验为静态指令 | 不会通过持续使用进化 |
| **SkillClaw** 🏆 | 群体进化 | 自动提取共性模式，全自动闭环，越用越强 |

---

## 七、快速上手

```bash
git clone https://github.com/AMAP-ML/SkillClaw.git && cd SkillClaw
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
skillclaw setup
skillclaw start --daemon
```

启动后默认端口 **30001**，健康检查端点 `/health`。

---

## 八、Dashboard

2026-04-22 新增，中英文双语：

```bash
skillclaw dashboard sync    # 同步本地/共享技能数据
skillclaw dashboard serve   # 启动可视化面板
```

功能：查看本地/共享 skill、验证进度、版本历史、会话追溯。

---

## 九、适用场景与局限

### 适合谁
- **个人开发者**：Agent 越用越强，无需手动维护 skill 库
- **团队**：一人经验，全组共享——A 踩过的坑 B 不用再踩
- **团队引入 Agent 的决策者**：群体进化可能成为竞争差异

### 当前局限
- 验证机制依赖 LLM 自身判断，生产环境需更严格验证
- 进化速度取决于会话数据量，低频场景较慢
- 多人协作的隐私控制不够细粒度

---

## 十、信息来源

| 来源 | 链接 | 类型 |
|---|---|---|
| GitHub | github.com/AMAP-ML/SkillClaw | 主仓库 |
| 论文 | arxiv.org/abs/2604.08377 | arXiv |
| 中文文档 | README_ZH.md（仓库内） | 中文说明 |
| 微信文章 | mp.weixin.qq.com/s/v1lhuJ78WUezrArIlYJ20Q | 实践测评（作者"李叔"） |

---

## 十一、归档文件

```
/mnt/usb/skills/SkillClaw/          ← 完整仓库克隆
├── README.md                       ← 英文文档
├── assets/README_ZH.md             ← 中文文档
├── skillclaw/                      ← Client Proxy 源码
├── evolve_server/                  ← Evolve Server 源码
├── scripts/                        ← 安装脚本
├── tests/                          ← 测试
├── skillclaw.pdf                   ← 论文 PDF
└── ...
```
