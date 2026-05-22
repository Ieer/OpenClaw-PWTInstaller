# PPT 技能生态全景参考 (2026-05-15)

**来源：** [26个PPT生成Skill，我做了一次系统梳理](https://mp.weixin.qq.com/s/gaNsToTe33IPXIddesJs1g) — ColaHub

本文梳理了 Agent Skills Hub 上 PPT & Presentation 分类的 26 个项目（含未收录的 2 个），总 Star 数超 7 万。

## 六大技术路线

| 路线 | 代表项目 | 核心特征 | 适合场景 |
|------|---------|---------|---------|
| **HTML 网页演示** | frontend-slides, guizang-ppt-skill, html-ppt-skill | 单文件 HTML，零构建，视觉上限极高 | 演讲分享、技术分享、Demo Day |
| **原生 PPTX** | ppt-master, mckinsey-pptx, ppt-agent-skills | 输出可编辑 .pptx，基于 python-pptx | 商业交付、客户可改 |
| **AI 图像驱动** | NanoBanana-PPT-Skills, gpt_image_2_skill | 用图像模型逐页生成视觉图 | 传播分发、高完成度视觉稿 |
| **MCP 协议层** | PPTAgent, Office-PowerPoint-MCP-Server | 给 LLM 操作 PPT 的能力 | 让 AI 直接读写 .pptx 文件 |
| **垂直场景专用** | academic-pptx-skill, ppt-translator | 专精学术/翻译/营销等场景 | 领域特定需求 |
| **综合设计平台** | open-design, docsagent | 涵盖原型/图片/视频/PPT | 完整设计流程 |

## 关键项目速查

### ⭐ ppt-master (16.6k ⭐) — 重磅发现
- **GitHub：** https://github.com/hugohe3/ppt-master
- **作者：** Hugo He（金融从业者）
- **技术路径：** SVG → 原生 DrawingML
- **核心能力：** PDF/DOCX/URL/MD → 可编辑 PPTX、模板复刻、动画、语音旁白、实时预览
- **注意：** 依赖 Claude Opus/Sonnet 大上下文窗口

### 其他高 Star 项目
| 项目 | Stars | 路线 | 亮点 |
|------|-------|------|------|
| open-design | 40.8k | 综合平台 | Claude Design 本地替代品 |
| frontend-slides | 17.5k | HTML | "show, don't tell" 三预览 |
| guizang-ppt-skill | 8.8k | HTML | 電子杂志风，强设计约束 |
| PPTAgent | 4.4k | 协议层 | 中科院，Reflective 生成 |
| html-ppt-skill | 3.8k | HTML | 36 主题，演讲者模式 |
| NanoBanana-PPT-Skills | 2.7k | 图像派 | 歸藏二号，AI 图像驱动 |

## 决策路径速查

| 需求 | 推荐工具 |
|------|---------|
| 咨询风 PPT，客户可改 | mckinsey-pptx / Mck-ppt-design-skill |
| 原生可编辑演示文稿 | **ppt-master** |
| 演讲酷炫 HTML Deck | frontend-slides / guizang-ppt-skill |
| Apple 风格特性卡片 | apple-bento-grid |
| 长 Word 报告转 PPT | odin-slides |
| 学术报告/会议演讲 | academic-pptx-skill / colloquium |
| PPT 翻译（保留格式） | ppt-translator |
| LLM 直接操作 PPT 文件 | Office-PowerPoint-MCP-Server |
| 全设计流程 | open-design |

## 与当前 pptx Skill 的关系

当前 pptx Skill 走的是 **原生 PPTX + HTML→PPTX** 路线，基于 python-pptx 和 html2pptx 工作流。与全景观比：

- **优势：** 已构建完整 html2pptx 流水线，含渐变栅格化、图表美化、设计系统、缩略图校验
- **差距：** ppt-master 的 SVG→DrawingML 路径在元素可编辑性和模板复刻上更优
- **可借鉴：** guizang-ppt-skill 的"保护美学"设计哲学、PPTAgent 的"反思式生成"机制

---

*本文档为外部参考归档，非实际技能实现。归档时间：2026-05-15。*
