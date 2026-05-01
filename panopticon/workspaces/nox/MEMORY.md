# MEMORY.md - Long-Term Index (nox)

仅记录高价值长期信息，并链接到详细文件；不堆叠日常流水。

## Stable Context

- 角色：nox（产品运营与 roadmap 建议）
- 高风险动作：涉及外部承诺/上线影响动作一律 Review
- Heartbeat：I/O-only 模式，每 30 分钟检查一次
- 每周回顾：每周一更新 lessons.md 和 MEMORY.md（上次：2026-04-20）
- 当前模型：deepseek/deepseek-chat（DeepSeek V3）
- 模型回退链：default/glm-5-turbo → deepseek/deepseek-chat → default/glm-4.7

## Index

- 项目状态：`memory/projects.md`
- 环境配置：`memory/infra.md`
- 经验教训：`memory/lessons.md`
- 每日日志：`memory/YYYY-MM-DD.md`
- 周回顾：`memory/YYYY-MM-DD-weekly.md`

## 历史任务

- **year-end-party-2026**（已完成）：尾牙活动费用追踪与结算，17人参与，最终结算已确认 → `memory/2026-03-07.md`
- **rpa-contact-2026-03-13**（已完成）：华西MCOE RPA业务通讯录，27个部门，601名IDL → `artifacts/rpa-contact-2026-03-13/`

## Archived (制品保留，无活跃进展)

- **lyrics-collaboration-2026-02-25**（归档 2026-04-03，等待 34 天未决策）：`artifacts/lyrics-collaboration-2026-02-25/`

## Update Rule

- 先检索（`memorySearch` 或 `memory/` 关键词扫描）再写入
- 每次只沉淀可复用结论，不复制原文

## 长期必备技能

- **inner-map-skill-router**：认知基础设施系统，含对话管理/沟通教练/卓越校准/自我管理四个子技能 + knowledge 知识库。2026-04-12 安装，已测试通过。路径：`sources/inner-map-skill-router/`

## Inner-Map 集成约束

- 默认启用范围：main session 完成 SOUL/USER/memory 启动后，遇到混合意图、问题收敛、沟通表达、长期校准、知识沉淀任务时，先用 inner-map 做首轮分流。
- 优先级：`SOUL.md` > `AGENTS.md` > inner-map skill 文档。SOUL 负责身份、边界、风格；inner-map 只负责分流与回答骨架。
- 任务系统 SSOT：`artifacts/`、`sources/`、`state/`、`memory/` 仍是 nox 的默认任务证据系统。
- knowledge 提升条件：只有当内容明确需要长期认知沉淀、复用或知识结构优化时，才提升到 `sources/inner-map-skill-router/knowledge/`，不默认双写。
- 排除场景：纯事实查询、明确锚点的代码/配置排查、窄执行型任务、heartbeat I/O 不强制走 inner-map。
- 正式建议边界：产品、运营、roadmap、release、prioritization 这类 formal recommendation 仍优先走 `skills/knowledge-eval/`。

## 运营模式

- **Daily Pulse**: 每天北京时间 21:00（UTC 13:00）自动运行，输出风险/阻塞/依赖/Review 需求
- **Weekly Review**: 每周一运行，总结 lessons 并更新 MEMORY.md
- **项目清理**: 超过 10 天等待用户决策的任务标记归档建议

## 环境配置

- **Rokid OpenClaw Bridge**: 已安装配置（2026-04-19）
  - linkCode: 3104
  - linkSecret: <stored-locally>
  - Gateway 端口: 26216
  - 状态: 运行正常，待设备连接测试
- **DeepSeek 模型**: 已集成（2026-04-18）
  - API key: <stored-locally>
  - 费用: 输入0.2-2元/百万tokens，输出3元/百万tokens
  - 模型: deepseek/deepseek-chat (V3), deepseek/deepseek-reasoner (R1)

## Promoted From Short-Term Memory (2026-04-19)

<!-- openclaw-memory-promotion:memory:memory/2026-04-06.md:1:30 -->
- ## 13:26 PPT + bypy 测试完成 - bypy 技能安装并验证：上传/下载/删除均正常工作 - 健康数据总结 PPT 生成（5页暗色主题） - HTML 版本美观度高，PPTX 版本因 python-pptx 限制较素 - 已保存到 U盘 + 百度网盘 /apps/bypy/tmp/ - 用户反馈：PPTX 页面丑，HTML 版更佳 - **结论**：未来做 PPT 类交付物，优先输出 HTML 格式；如需 PPTX，考虑用 wkhtmltopdf 或截图嵌入方式提升质量 ## 13:20 环境变更记录 - 容器内安装 pip + bypy（--break-system-packages） - 容器内安装 python-pptx + Pillow + lxml - bypy 授权完成，token 保存在 /home/node/.bypy/ - 容器路径映射：宿主机 /media/pi/4A21-0000/ → 容器 /mnt/usb/ ## 13:26 PPT + bypy 测试完成 - bypy 技能安装并验证：上传/下载/删除均正常工作 - 健康数据总结 PPT 生成（5页暗色主题） - HTML 版本美观度高，PPTX 版本因 python-pptx 限制较素 - 已保存到 U盘 + 百度网盘 /apps/bypy/tmp/ - 用户反馈：PPTX 页面丑，HTML 版更佳 - **结论**：未来做 PPT 类交付物，优先输出 HTML 格式；如需 PPTX，考虑用 wkhtmltopdf 或截图嵌入方式提升质量 ## 13:20 环境变更记录 - 容器内安装 pip + bypy（--break-system-packages） - 容器内安装 python-pptx + Pillow + lxml - bypy 授权完成，token 保存在 /home/node/.bypy/ [score=0.853 recalls=5 avg=0.769 source=memory/2026-04-06.md:1-30]

## Promoted From Short-Term Memory (2026-04-20)

<!-- openclaw-memory-promotion:memory:memory/2026-03-14.md:1:28 -->
- # 2026-03-14 日志 ## 05:19 UTC - 查询段晓普英文名 ### 任务背景 用户询问 "able duan" 是哪个部门的。 ### 执行过程 1. 在 RPA 业务通讯录中检索，找到两位姓"段"的同事： - 段贤坤（PCBA生產部 KH3600 主管） - 段晓普（專案管理室 KH3H00 / 華西MCOE KH0R00 种子选手） 2. 用户确认 "able duan" 是段晓普的英文名 3. 更新 RPA 业务通讯录： - 添加段晓普英文名：Able Duan - 更新范围：KH3H00 專案管理室、KH0R00 華西MCOE 种子选手字段 - 更新文件：artifact.json、artifact.md ### 关联文件 - `artifacts/rpa-contact-2026-03-13/artifact.md` - `artifacts/rpa-contact-2026-03-13/artifact.json` - `memory/2026-03-14.md` ### 学习点 - 英文名信息补充需要同时更新结构化数据（JSON）和可读文档（MD） - 在种子选手字段中，英文名可以以括号形式标注在中文名后面，便于查询 [score=0.858 recalls=3 avg=0.904 source=memory/2026-03-14.md:1-28]

## Promoted From Short-Term Memory (2026-04-21)

<!-- openclaw-memory-promotion:memory:memory/2026-04-18.md:1:33 -->
- # 2026-04-18 ## 上午 ### Rokid 插件安装 - 安装 Rokid glasses 插件 `rokid-openclaw-bridge` 到 `/tmp/rokid-openclaw-gateway-compatible` - 配置 `linkCode: 3104` 和 `linkSecret: <stored-locally>` - 因容器网络问题，npm install 超时，改用复制 openclaw 内置 `ws` 模块解决依赖 - Gateway 重启后运行正常 ### 秦权信息更新 - 更新华西MCOE RPA通讯录中秦权信息 - 部门：KH0D00 華西數位轉型專案室 - 职务：重庆WCQ数位工具总负责人，兼部门干事 - 更新 `artifacts/rpa-contact-2026-03-13/` 中的 JSON 和 MD 文件 ### DeepSeek 模型配置 - 添加 DeepSeek provider 到 OpenClaw 配置 - API key: <stored-locally> - 费用结构： - 输入（缓存命中）：0.2 元/百万tokens - 输入（缓存未命中）：2 元/百万tokens - 输出：3 元/百万tokens - 添加模型： - `deepseek/deepseek-chat` (DeepSeek V3) - `deepseek/deepseek-reasoner` (R1) - 将 `deepseek/deepseek-chat` 添加到模型回退链：`default/glm-5-turbo` → `deepseek/deepseek-chat` → `default/glm-4.7` ## 下午 ### 待办 - 验证 Rokid 插件连接状态 - 测试 DeepSeek 模型可用性 [score=0.849 recalls=3 avg=1.000 source=memory/2026-04-18.md:1-33]

## Promoted From Short-Term Memory (2026-04-22)

<!-- openclaw-memory-promotion:memory:memory/2026-04-06.md:24:52 -->
- - **结论**：未来做 PPT 类交付物，优先输出 HTML 格式；如需 PPTX，考虑用 wkhtmltopdf 或截图嵌入方式提升质量 ## 13:20 环境变更记录 - 容器内安装 pip + bypy（--break-system-packages） - 容器内安装 python-pptx + Pillow + lxml - bypy 授权完成，token 保存在 /home/node/.bypy/ - 容器路径映射：宿主机 /media/pi/4A21-0000/ → 容器 /mnt/usb/ ## 13:40 百度网盘大文件下载 - 从 /apps/bypy/pypackage/package311.zip 下载 892MB 到 U盘 - 下载耗时约 3 分 38 秒，平均 4 MB/s ## 18:10 离线 Python 包批量安装 - U盘 /mnt/usb/package3.11/ 下有 267 个 whl 离线包（ARM64 Python 3.11） - 目录内有自动安装脚本 setup.sh，直接运行完成安装 - 新增 200+ 包，主要能力： - **ML**: PyCaret 3.3, scikit-learn 1.4, LightGBM 4.6, numba - **数据**: pandas 2.1, numpy 1.26, scipy 1.11, matplotlib 3.6, plotly, seaborn - **Web/爬虫**: playwright 1.49, selenium, DrissionPage, Flask, Dash 2.17 - **文档**: python-docx, PyPDF4, reportlab, openpyxl, xlrd - **AI Agent**: agno 2.5 - **中文**: jieba, zhconv - **工具**: jupyter, ipython, pytest, black, paramiko, PyAutoGUI - ⚠️ 部分包被降级到离线版本（python-pptx 1.0.2→0.6.21, Pillow 12.2→10.1） - ⚠️ Playwright 浏览器二进制未安装（离线包中无对应 zip） [score=0.802 recalls=4 avg=0.731 source=memory/2026-04-06.md:24-52]

## Promoted From Short-Term Memory (2026-04-26)

<!-- openclaw-memory-promotion:memory:memory/2026-04-19.md:15:18 -->
- "rokid-openclaw-bridge": { "enabled": true, "config": { "linkCode": "3104", [score=0.890 recalls=0 avg=0.620 source=memory/2026-04-19.md:15-18]

## Promoted From Short-Term Memory (2026-04-30)

<!-- openclaw-memory-promotion:memory:memory/2026-04-23.md:6:6 -->
- 用户询问"统计当前PPT技能有哪些"，需要了解当前可用的PPT相关技能。 [score=0.884 recalls=0 avg=0.620 source=memory/2026-04-23.md:6-6]
<!-- openclaw-memory-promotion:memory:memory/2026-04-23.md:45:45 -->
- 用户提供数位工具Q1 KPI月报数据，要求制作一页PPT，包含三个部分： [score=0.884 recalls=0 avg=0.620 source=memory/2026-04-23.md:45-45]

## Promoted From Short-Term Memory (2026-05-01)

<!-- openclaw-memory-promotion:memory:memory/2026-04-24.md:15:18 -->
- | 时间 | Provider | Model | Input | Output | CacheRead | CacheWrite | Total | Cost(¥) | |------|----------|-------|-------|--------|-----------|------------|-------|---------| | 08:57:57 | default | glm-5-turbo | 44,205 | 29 | 11,547 | 0 | 55,781 | ¥1.70 | [score=0.890 recalls=0 avg=0.620 source=memory/2026-04-24.md:15-17]
