### 核心约束
- **底部安全边距**: ≥ 50pt (最小36pt/0.5", 建议50pt预留缓冲)
- **顶部边距**: 100-110pt (包含固定header时)
- **侧边距**: 40-50pt (左右各)

### 字体大小（pt）

| 元素 | 推荐范围 | 安全值 | 避免 |
|------|----------|--------|------|
| h1 (标题) | 32-38pt | 36pt | >42pt |
| h2 (副标题) | 24-28pt | 26pt | >30pt |
| h3 (章节标题) | 20-24pt | 22pt | >26pt |
| p (正文) | 14-16pt | 15pt | >18pt |
| 引用/强调 | 16-20pt | 18pt | >22pt |
| 列表项 | 14-16pt | 15pt | >17pt |

### 间距（pt）

| 类型 | 推荐 | 安全值 | 避免 |
|------|------|--------|------|
| h1 margin-bottom | 15-20pt | 18pt | >25pt |
| h2/h3 margin-bottom | 12-15pt | 13pt | >18pt |
| p margin-bottom | 8-12pt | 10pt | >15pt |
| 列表项 margin-bottom | 3-5pt | 4pt | >8pt |
| 内容区 padding | 12-18pt | 15pt | >25pt |
| 元素组 margin-top | 10-15pt | 12pt | >20pt |
| 最后元素 margin-bottom | 0pt | 0pt | >0pt |

### 布局安全值（从顶部计算）

```css
.header {
  height: 80pt;           /* 固定header高度 */
  margin-bottom: 20pt;    /* header下方间距 */
}

.content {
  margin: 100pt 50pt 60pt 50pt;  /* 上 右 下 左 */
  /* 实际可用高度 ≈ 405 - 100 - 60 = 245pt */
}
```

### 常见错误模式 → 修复

| 问题 | 典型值 | 修复为 |
|------|--------|--------|
| 底部不足 0.06" | margin-bottom: 40pt | 60pt |
| 标题过大 | h1: 42pt | 36pt |
| padding过大 | padding: 25pt | 15pt |
| 列表项间距大 | margin-bottom: 8pt | 4pt |
| 最后元素有底距 | margin-bottom: 15pt | 0pt |
| 固定footer太高 | margin-top: 25pt | 10pt |

### 保守设计原则（首次即通过）
- ✅ 底部留 50pt（非 36pt最小值）
- ✅ h1 用 36pt（非 42pt）
- ✅ 正文 15pt（非 18pt）
- ✅ padding 用 15pt（非 20-25pt）
- ✅ 列表用 `<ul>` + margin-bottom: 4pt
- ✅ 最后一个元素 margin-bottom: 0
