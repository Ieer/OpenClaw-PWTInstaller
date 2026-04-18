# SpeechSynth Phase 1 Playbook -- speech-script.json 真源定义

## 目标

基于需求、资料简报、大纲、页面规划与最终 HTML，输出一份可同时服务于：

1. 独立阅读的演讲稿文件
2. PNG PPTX speaker notes
3. SVG PPTX speaker notes

的统一真源 `speech-script.json`。

---

## 生成原则

### 1. 讲述要比页面多一层信息，但不能发明页面没有依据的事实

- 屏幕上已经完整写出来的句子，不要 1:1 机械朗读
- 你要补的是：解释、强调、转折、口语化收束、页间衔接
- 所有数据、结论、案例必须能在 `brief / outline / planning / slides` 中找到依据

### 2. notes 要能直接口播

- 用自然语言写，不要写成大纲 bullet 残片
- 每页允许 1-3 个自然段；短页可以是单段，复杂页可以分段
- 优先帮助讲者控制“这一页为什么讲、强调什么、怎么过渡到下一页”

### 3. 节奏要与 deck 的叙事一致

- 首页 notes 负责开场定题
- 中段页面 notes 负责解释数字、逻辑和对比关系
- 收尾页 notes 负责行动号召或总结闭环

---

## JSON 合同（强制）

输出必须是**原始 JSON 对象**，禁止包裹代码围栏。字段合同如下：

```json
{
  "deck_title": "<整套演讲标题>",
  "language": "<zh-CN | en-US | ...>",
  "summary": "<整套演讲的总说明，可选但建议>",
  "total_pages": 8,
  "pages": [
    {
      "page": 1,
      "slide_title": "<该页标题>",
      "estimated_seconds": 45,
      "speaker_notes": "<可直接写入 PPT notes 的自然语言讲稿>",
      "transition_to_next": "<到下一页的过渡句，可选>"
    }
  ]
}
```

---

## 字段细则

- `deck_title`：整套 deck 的演讲标题，不能为空
- `language`：讲稿语言标识，不能为空
- `summary`：建议填写 1 段，帮助独立阅读时快速理解整套叙事
- `total_pages`：建议填写，并与 `pages` 长度一致
- `pages[].page`：必须从 1 开始连续编号
- `pages[].slide_title`：必须与该页主题或标题一致
- `pages[].estimated_seconds`：建议填写，通常 15-180 秒
- `pages[].speaker_notes`：必须非空，长度要足够形成可口播语句
- `pages[].transition_to_next`：可选，但仅在确有必要时填写

---

## 写作提醒

- 面向高管 / 投资人 / 客户 / 培训学员的语气应该不同，必须跟着 `requirements-interview.txt` 走
- 如果某页是图表页，notes 要负责“读图”而不是“再写一遍图例”
- 如果某页信息很少，notes 需要补足该页在整套叙事中的功能