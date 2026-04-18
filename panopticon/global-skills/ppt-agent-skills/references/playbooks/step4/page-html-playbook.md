# Page HTML Playbook -- 单页 HTML 设计稿

## 目标

忠实还原 planning JSON 里的骨架与精神，运用 `resource_loader.py resolve` 的解析能力，将抽象组件组装成极具高级设计感的**单页自包含 HTML**。

---

## Phase 1：骨架理解（不得跳过）

读取 `planning{n}.json` 的以下字段作为本阶段的硬约束：

| 字段 | HTML 阶段的含义 |
|------|--------------|
| `page_type` / `layout_hint` | 决定整体骨架与页面自由度 |
| `focus_zone` | 决定哪个卡片/区域应该有最大视觉权重 |
| `negative_space_target` | 决定留白比例（high=宽松 / medium=适中 / low=密集）|
| `cards[].role` / `cards[].card_style` | 决定主次顺序与卡片存在感 |
| `cards[].card_id` | 要在 HTML 中逐一落地，并映射到 `data-card-id` |
| `cards[].content_budget` | 限制每张卡片的承载量，防止溢出 |
| `director_command` / `decoration_hints` | 决定镜头感、装饰层次和实现边界 |
| `source_guidance` / `must_avoid` | 决定证据呈现方式与禁止动作 |
| `image.mode` | 严格按下面第 3 条执行 |

---

## Phase 2：资源正文消费（强制执行，不得跳过）

```bash
python3 SKILL_DIR/scripts/resource_loader.py resolve --refs-dir REFS_DIR --planning PLANNING_OUTPUT
```

脚本返回 planning 中引用的每个资源的**完整正文实现**，包含：
- 组件的 HTML 结构骨架（含 class 命名示例）
- 推荐的 CSS 参数（间距、字号、颜色变量用法）
- 数据格式要求（如 chart 的 data 格式）

**你应当以此作为骨架参考，并在此基础上享有极大的创意与改写自由度。后续的像素级图审（Visual QA）会负责纠偏。**

特别注意：
- 虽然 resolve 提供了基础结构，但你拥有**非常高的设计自由权**，鼓励用更多现代、创意的结构代替或增强组件。
- 允许在保留核心业务语义的情况下大胆打破标准模板感。
- `process` 这类没有独立 block 文件的 card_type，可根据你自身的高级审美，自由借助 CSS 创新重构。

---

## Phase 3：图片模式严格执行

| image.mode | HTML 要做什么 | 绝对禁止 |
|-----------|-------------|---------|
| `generate` / `provided` | 用 `source_hint` 路径渲染 `<img src>` 或 `background-image: url()` | 不得用占位色块替代真实图 |
| `manual_slot` | 渲染明确尺寸的图片占位框（带虚线边框 + 文字说明"[图片替换位]"）| 不得删掉或做成看不出来的空白 |
| `decorate` | 使用内联 SVG、CSS 渐变、几何色块、大字水印、圆圈装饰等内部视觉语言补足氛围 | 不得留空白大洞，不得放空的 `<div>` |

---

## Phase 4：卡片落地对账（强制）

- `planning.cards[]` 中的每一张卡都必须有一个对应的 HTML 根节点。
- 每个根节点都要带 `data-card-id="<card_id>"`，便于 Review 阶段与 planning 对账。
- `role = anchor` 的卡必须成为全页第一视觉落点；`support/context` 退后，但不能消失。
- 若卡片带 `chart.chart_type`，最终图表类型必须与 planning 保持一致；不要把 `comparison_bar` 偷换成普通 list。
- 若 `source_guidance` 要求保留来源，至少在卡片 footer / caption / 注释位中给出来源提示。

---

## Phase 4.5：图片 + 正文 + 图表共存排版合同（图文并茂页强制）

当一页同时存在真实图片、正文和图表时，不允许把三者当作可以随意堆叠的普通卡片。你必须先明确主次关系，再决定空间分配。

### 先定主次，再定空间

- 一页只能有一个第一视觉锚点：图片、图表、超大数字/标题三者只能选一个做主角。
- 正文承担解释职责时，必须拥有独立阅读区，不能沦为挂在图片区或图表缝隙里的注释碎片。
- 图片如果只是氛围或场景，不要和图表争主锚；让它退到侧栏、次级卡片或背景层。
- 图表如果承担结论，就必须获得完整标签空间，不得被图片或 caption 挤压到危险字号。

### 推荐骨架（优先从这里选）

1. 图表主锚 + 侧栏配图 + 短正文
   - 适合数据证据页。
   - 图表区宽度优先 `46-58%`。
   - 图片区宽度优先 `28-36%`。
   - 正文区可与图表同列，但净宽必须保持 `320px+`。

2. 图片主锚 + 正文/图表纵向支撑
   - 适合案例页、场景证据页。
   - 主图片区宽度优先 `40-48%`，除半画册式页面外不要超过全页一半。
   - 另一列用于“短正文 + 小图表”上下排布；若图表标签较多，就改成“图表上 + 正文下”。

3. 上方短导语 + 下方双栏（图 / 图表）
   - 只适用于正文很短的页。
   - 顶部导语总高度优先控制在 `88-120px`。
   - 下方双栏必须给图片和图表分别留完整盒子，不允许再把正文塞进中缝。

### 文本合同

- 承担解释职责的正文列净宽不得低于 `320px`；正文超过 4 行时，优先给到 `360-420px`。
- 正文块与图片块、图表块之间至少留 `20-28px` 间距；高密度页优先 `24px+`。
- 图片旁正文默认不超过 3 个段落或 4 个 bullet；超过后优先拆栏或删减，不要继续向下堆叠。
- 图片 caption、图表来源、来源注释都应归属于各自容器底部，不要漂浮在图片区和图表区之间的缝隙中。

### 图片容器合同

真实图片必须落在明确的媒体容器里，而不是散落在页面上：

```css
.media-shell {
  position: relative;
  overflow: hidden;
  min-width: 280px;
  min-height: 180px;
  border-radius: var(--card-radius);
}

.media-shell img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.media-caption {
  margin-top: 10px;
  font-size: 11px;
  line-height: 1.45;
}
```

- `landscape` 图默认优先横向容器；`portrait` 图默认优先窄列或竖向卡片；`square` 图默认优先中小型证据框。
- 只有当保留完整主体比铺满容器更重要时，才把 `object-fit` 改为 `contain`；改成 `contain` 后必须补底色或边框，避免像破图。
- 不要把 caption 直接压在复杂图片上；如果必须覆盖，先加稳定遮罩或底板。

### 图表容器合同

- 图表与图片共存时，图表容器最小高度优先 `220-260px`；复杂图表宁可放大，也不要被图片挤成一条带。
- 图表标签区必须有自己的内边距，不得与图片边缘直接贴死。
- 图表区背景与图片区背景要可区分，避免观众误以为图表只是图片上的浮层。
- 图表来源、备注优先放在图表卡片底部，不要跨卡片漂移到图片区下方。

### 绝对禁忌

- 禁止把正文直接铺在高细节图片上，而不加遮罩、底板或独立文本容器。
- 禁止图片、图表、正文沿同一纵向路径从上堆到下，逼近页脚安全区。
- 禁止把图片裁到只剩难以识别的局部，却还要求它承担证据角色。
- 禁止为了塞下三种元素而把正文压到 `13px` 以下、caption 压到 `10px` 以下。
- 禁止图片和图表相互跨层覆盖，除非这页本质上就是叠加信息图，且文本对比已被稳态保护。

### 自检追问

1. 图片、正文、图表里，谁是第一视觉锚点？其余两者是否明确退让？
2. 去掉图片后，这页论证是否仍成立？去掉图表后是否仍成立？如果两个答案都是否，说明职责分工不清。
3. 正文是否拥有独立阅读区，而不是挂在图片区或图表缝隙里的说明碎片？
4. 最底部一排元素里，是否同时出现 caption、来源、页脚、图表标签四种信息？如果是，底部已经过载。

---

## Phase 5：画布物理红线（不可违反）

```css
* {
  box-sizing: border-box; /* 像素级排版防崩核心 */
}

body {
  width: 1280px;
  height: 720px;
  overflow: hidden;
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale; /* 保障文字渲染精度 */
}
```

**像素级渲染安全防线（涉及无头浏览器最终出图质量，极度重要）：**
- **流体坍缩预防**：在高度自由发挥时，`flex` / `grid` 极易出现子项挤压坍缩。凡是重要卡片或必须撑开的区域，务必使用 `min-width`, `min-height` 或 `flex-shrink: 0`。
- **行高裁剪预防**：文字的 `line-height` 若低于 `1.3`，部分英文小写字母下端极其容易被隐形裁剪，正文需保持合理行高。
- **边框与阴影溢出**：所有的边框宽度、`box-shadow` 都可能溢出原有容器。借助于 `box-sizing: border-box`，确保 padding 和 border 在规划宽度内。

- **禁止** `width: 100%; height: 100%` 然后依赖父容器
- **禁止** `transform: scale()` 缩放 hack
- **禁止** 引用外部 CSS 文件（如 `common.css`、`deck.css`）

### 统一导航骨架（强制 -- 保证全 deck 视觉一致性）

每个页面由独立的 PageAgent 生成，**必须**使用统一的标题区和页脚区 HTML 骨架，避免拼装后各页标题/页脚形态各异。骨架规范详见 `design-specs.md` A 节「统一导航骨架合同」，核心规则如下：

| page_type | 标题区 | 页脚区 |
|-----------|--------|--------|
| `content` / `toc` | **强制** `header.slide-header > span.overline + h1.page-title`，`position:absolute; top:20px` | **强制** `footer.slide-footer`，`position:absolute; bottom:12px` |
| `section` | **自由**（章节标题是设计主角） | **强制** 同上 |
| `cover` / `end` | **自由** | **可选** |

**视觉创意不受影响**：overline 内容、page-title 字号、装饰线、页脚风格（W12 终端/印章/进度条）都可按风格变化。统一的只是 **HTML 结构和定位方式**。

### 导出安全区与保守排版（强制优先于炫技）

如果本页存在正文、列表、图表、表格或页脚，则默认按以下保守安全区做首版布局：

```css
.content-safe-zone {
  position: absolute;
  top: 104px;
  left: 80px;
  right: 80px;
  bottom: 92px;
}
```

优先遵守这些安全值：
- 顶部内容起点控制在 `96-112px`，不要压到标题区。
- 左右边距优先 `72-88px`，高密度图表/表格页优先用 `80px` 左右。
- 底部安全区优先 `84-96px`，避免页脚贴边、字形下沉被切和导出裁边。
- 主内容总高度尽量控制在 `520-540px`，超过后优先减内容，不要先硬缩放。
- 页面标题优先 `24-30px`，正文 `14-17px`，列表 `14-16px`，来源注释 `10-12px`。
- 正文 `line-height` 保持 `1.45-1.7`，标题 `1.1-1.25`，最后一个正文元素 `margin-bottom: 0`。

高风险版式的默认保守解法：
- 图表/表格页优先左右分栏或整页主图，不要做“标题 + 多段正文 + 图表 + 注释”纵向堆叠。
- 多卡片信息页尽量控制在 2-4 个主卡片；anchor 已经很大时，support 只保留 1-2 个关键证据点。
- 图片页要给正文和图片各自留独立空间，不让两者争同一条纵向路径。

出现以下信号说明你已经进入危险区，必须立刻收敛：
- 页脚与正文的垂直距离小于 `24px`。
- 单卡正文超过 6 行仍不分栏、不裁剪。
- 图表标签必须旋转或挤成两行才能放下。
- KPI 数字已经占满一整列，support 内容被迫缩成注释字级。
- 页面必须依赖 `scale()`、负 margin 或大幅绝对定位硬塞回画布。

## Phase 5.5：PPTX 友好 HTML 兼容边界（强制）

这一步不是限制你做设计，而是防止“浏览器正常、PPTX 失真”的实现方式混入最终 HTML。

### 文本与语义

- 所有正文必须落在明确文本标签中：`h1-h3`、`p`、`li`、`span`。
- 列表必须使用 `ul` / `ol`，不要手写项目符号。
- 重要文案不要只存在于 `::before` / `::after` 中。
- 关键事实、数字、来源、主结论不得只做成背景图或纯装饰路径。

### 结构与容器

- 卡片、面板、色块、描边、阴影优先放在 `div` / `section` 容器层处理。
- 重要布局块显式设置 `min-width`、`min-height` 或 `flex-shrink: 0`，防止截图时被挤塌。
- 关键信息不要依赖深层 transform 嵌套定位。
- 每个 planning card 继续保留根节点 `data-card-id`，便于 Review 和对账。

### CSS 边界

优先使用：
- `flex` / `grid`
- 适量 `position: absolute`
- 纯色、半透明色块、常规阴影
- 常规圆角、边框、线性渐变背景
- 内联 SVG 作为装饰或图表

谨慎使用，且不要承载核心信息：
- `clip-path`
- `mask-image`
- `mix-blend-mode`
- `backdrop-filter`
- 加在文字上的复杂 `filter`
- 过深层级的 transform 嵌套

绝对禁止：
- 动画、transition、滚动交互承载内容
- 用 `scale()` 把超出的页面硬缩回画布
- 让核心文案依赖 hover、展开、折叠或脚本执行后才出现

### 图片、图标与复杂效果

- 图片必须使用真实路径，并显式加 `object-fit: cover` 或 `contain`。
- 若图标、复杂渐变、光斑纹理对视觉效果至关重要，优先预渲染成图片再放进 HTML。
- 装饰层不承载事实、数字、来源和主结论。
- 不确定 SVG 链路是否稳定的效果，优先降级为图片资源，而不是强行保留 CSS 黑科技。

### 导出一致性自问

写 HTML 时持续自问：
1. 去掉阴影、滤镜和装饰后，这页核心信息是否仍然成立？
2. 把这页走一遍 PNG 和 SVG，两条链路是否都会保住主标题、数据和图像位置？
3. 如果某个效果失真，是否可以用更朴素但稳定的做法达到 80% 的视觉目标？

---

## Phase 6：风格变量严格绑定

从 `style.json` 的 `css_variables` 提取所有变量，写入 HTML 的 `:root`：

```css
:root {
  --bg-primary: [从 style.json 取];
  --bg-secondary: [从 style.json 取];
  --card-bg-from: [从 style.json 取];
  --card-bg-to: [从 style.json 取];
  --card-border: [从 style.json 取];
  --card-radius: [从 style.json 取];
  --text-primary: [从 style.json 取];
  --text-secondary: [从 style.json 取];
  --accent-1: [从 style.json 取];
  --accent-2: [从 style.json 取];
  --accent-3: [从 style.json 取];
  --accent-4: [从 style.json 取];
  --font-primary: [从 style.json font_family 取];
}
```

- `design_soul`：用来校准情绪，不得直接抄成页面文案
- `variation_strategy`：控制这一页的变化幅度，避免与相邻页同构复制
- `decoration_dna.forbidden`：硬边界，违反即自动不达标
- `decoration_dna.recommended_combos`：优先采用
- `decoration_dna.signature_move`：跨页识别锚点，必须出现

---

## Phase 7：你是设计师，不是渲染引擎

> **核心理念**：planning JSON 是你的设计意图蓝图，resource resolve 的组件正文是你的材料库。你的工作不是“照搬组件拼装”，而是“为这一页的内容创造最佳的视觉表达”。

**你的创意权利：**
- CSS 实现拥有最高自由权，一切以“令人惊艳的视觉体验”为最高目标
- 布局手段根据内容特征自主选择：Grid/Flex/absolute/混合定位
- resolve 输出的组件正文是起点，你可以大幅改写、重组、融合
- 但只在不破坏上面“导出安全区”和“HTML 兼容边界”的前提下使用高阶技巧；有风险时优先选择更稳的实现

**设计独立性自检（追问：这页的设计是从内容出发的吗？）**：
- 本页的布局结构是为本页的 `page_goal` 和 `director_command` 量身定做的吗？
- 视觉锚点的位置和大小是否反映了本页内容的主次关系？
- 如果把本页的内容换成完全不同的主题，这个布局还能用吗？（如果能，说明你在套模板）

**后续保障**：你在此阶段的所有创意实现都有像素级图审（Review）兜底修正，不必束手束脚，但不要把 Review 当成替你收拾基础导出事故的借口。

---

## Phase 8：完成条件

写入目标 HTML 文件后：
- 文件非空
- 无语法错误（HTML 标签闭合完整）
- 没有明显乱码或缺失的 CSS 变量引用
- `planning.cards[]` 全部能在 HTML 中找到对应的 `data-card-id`

发送 FINALIZE 信号，然后等待 Review 阶段指令。
