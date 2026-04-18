# SpeechSynth Phase 2 Playbook -- speech-script.json 自审清单

## 目标

对 Phase 1 产出的 `speech-script.json` 做字段合同、事实一致性和讲述可用性三重验收。

---

## 自审动作流程

1. 直接读取 `speech-script.json`
2. 对照 `outline.txt` 与最终 `slides/slide-N.html` 逐页检查
3. 一旦发现问题，原地改写同一个 JSON 文件
4. 修改后重新检查，最多允许 2 轮

---

## 6 项检查清单

| # | 核查重点 | 处理方式 |
|---|--------|---------|
| 1 | 页数与编号 | `pages[].page` 必须从 1 连续到 `TOTAL_PAGES`，少页、跳号、重复都要立即修复。 |
| 2 | 标题对齐 | `slide_title` 必须和该页真实主题一致，不能把第 3 页标题写到第 4 页。 |
| 3 | 事实边界 | `speaker_notes` 不得出现 slides / outline / brief 中没有依据的数字、客户名、结论。 |
| 4 | 口语可讲性 | notes 不能只是词组堆砌，必须是讲者可以直接说出口的自然语言。 |
| 5 | 冗余度 | 不要整段照抄页面正文；notes 应该补解释、强调和转场，而不是复制屏幕文案。 |
| 6 | 时长与衔接 | `estimated_seconds` 若填写，应在合理范围；`transition_to_next` 若填写，应服务于下一页衔接而不是重复本页内容。 |

---

## FINALIZE 签名契约

只有在 6 项检查全部通过后，才能发送：

```
FINALIZE: 自审通过
- speech_script: [SPEECH_OUTPUT 路径]
- 自审轮数: N
- 修复发现: [列举修复项，若无填 无]
```