# Structured UI Mode -- CLI 原生结构化采访

## 提炼与丰富化要求（执行纪律）

1. **极端静默交互**：直接输出结构组件，严禁穿插任何“询问原因/步骤说明/口语寒暄”。
2. **拒绝干瘪，提供高密度备选项**：不要只给“商务”、“极客”这种干瘪词汇。必须在每个 option 的 `label` 或 `description` 中提炼出具体的审美/逻辑画面。
   -*反例*：`{label: "商务风"}`
   -*正例*：`{label: "极简商务", description: "Apple-Style 大留白，精炼去图表，适合高级汇报"}`
3. **闭环式诱导**：所有核心字段都不允许开放填空，全部分类转化成极具专业启发性的选项（且带“其他”口子），诱导用户提供能让下游吃饱的丰满参数。
4. **单页简报显式入口**：`expected_pages` 必须提供“1页简报 / Executive one-pager（给老板一页看完，结论+KPI+风险+行动闭环）”；`page_density` 必须区分“高密度但可读”和“容量极大/情报板”。

## 组件格式骨架

使用系统支持的最优组件（如 `question/header/id/options`），优先调用能力名可表现为 `AskUserQuestion` 或 `request_user_input`，确保结构如下：

```text
questions: [
  {
    header: "...",
    id: "...",
    question: "...",
    options: [
      { label: "...", description: "..." }
    ]
  }
]
```

## 能力兼容说明

- 若宿主环境把结构化提问能力命名为 `AskUserQuestion`，直接按该接口的对象结构组织问题。
- 若宿主环境把结构化提问能力命名为 `request_user_input`，同样按 `question/header/id/options` 语义组织问题。
- 名称可以不同，但只要支持 `question/header/id/options` 这组字段，就必须使用结构化采访 UI，而不是退回纯文本问答。
