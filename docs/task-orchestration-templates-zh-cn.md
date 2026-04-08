# 任务编排模板

这份文档不是讲“怎么建任务”，而是讲“怎么把任务建得更好用”。

当前 Mission Control 的任务接口字段很少，只有 `title`、`status`、`assignee`、`tags`，外加任务评论。正因为字段少，任务本身就要写得更明确，才能减少来回追问，提升用户体验。

## 先看几个具体例子

下面这些例子不是模板，是可直接照着用的任务写法。

### 例子 1：每周复盘

你要做每周复盘，不要把所有事压成一个笼统任务，而是拆成明确分工：

```json
{
  "title": "汇总过去 7 天各 Agent 活跃情况",
  "status": "INBOX",
  "assignee": "metrics",
  "tags": ["weekly-review", "reporting"]
}
```

```json
{
  "title": "基于复盘结果调整路线优先级",
  "status": "INBOX",
  "assignee": "nox",
  "tags": ["weekly-review", "roadmap"]
}
```

```json
{
  "title": "把复盘结果整理成可发布周报",
  "status": "INBOX",
  "assignee": "writing",
  "tags": ["weekly-review", "summary"]
}
```

```json
{
  "title": "把结论转成后续待办",
  "status": "INBOX",
  "assignee": "personal",
  "tags": ["weekly-review", "todo"]
}
```

为什么这样更好：

- `metrics` 先把事实整理出来，避免讨论建立在模糊印象上。
- `nox` 负责路线判断，减少用户在多个任务间来回切换。
- `writing` 把结果变成可读内容，用户看完就能直接转发。
- `personal` 把结论落成下一步待办，减少复盘后“知道了但没行动”的落差。

### 例子 2：邮件营销

你要做一次邮件营销，也不要把策略、文案、效果分析塞在同一个任务里：

```json
{
  "title": "制定本次邮件营销策略",
  "status": "INBOX",
  "assignee": "growth",
  "tags": ["email-marketing", "strategy"]
}
```

```json
{
  "title": "撰写邮件内容并整理发送思路",
  "status": "INBOX",
  "assignee": "email",
  "tags": ["email-marketing", "copy"]
}
```

```json
{
  "title": "复盘邮件打开率和转化表现",
  "status": "INBOX",
  "assignee": "metrics",
  "tags": ["email-marketing", "analysis"]
}
```

```json
{
  "title": "判断是否继续推进为长期项目",
  "status": "INBOX",
  "assignee": "nox",
  "tags": ["email-marketing", "decision"]
}
```

为什么这样更好：

- `growth` 先定方向，避免一开始就写内容却没有目标。
- `email` 负责内容和发送思路，分工更自然。
- `metrics` 负责结果分析，能把“做了什么”和“有没有效果”分开。
- `nox` 负责是否继续投入，避免短期活动和长期路线互相打架。

### 例子 3：个人健康

你要管理个人健康，也可以拆成计划、执行和总结三层：

```json
{
  "title": "制定饮食、作息和运动计划",
  "status": "INBOX",
  "assignee": "health",
  "tags": ["health", "plan"]
}
```

```json
{
  "title": "把健康计划整合进提醒和日程",
  "status": "INBOX",
  "assignee": "personal",
  "tags": ["health", "schedule"]
}
```

```json
{
  "title": "汇总长期趋势并生成可读报告",
  "status": "INBOX",
  "assignee": "metrics",
  "tags": ["health", "report"]
}
```

为什么这样更好：

- `health` 负责制定可执行计划，避免任务只停留在“想改善一下”。
- `personal` 负责提醒和日程整合，真正帮助用户坚持执行。
- `metrics` 负责趋势总结，让健康管理有反馈闭环。

### 例子 4：交易或财务操作

你要处理交易或财务操作时，建议把操作、统计和路线判断分开：

```json
{
  "title": "整理当前交易或财务操作视角",
  "status": "INBOX",
  "assignee": "trades",
  "tags": ["finance", "ops"]
}
```

```json
{
  "title": "统计交易结果并生成报表",
  "status": "INBOX",
  "assignee": "metrics",
  "tags": ["finance", "report"]
}
```

```json
{
  "title": "判断是否纳入整体路线并避免冲突",
  "status": "INBOX",
  "assignee": "nox",
  "tags": ["finance", "roadmap"]
}
```

为什么这样更好：

- `trades` 负责操作视角，不把财务判断和执行混在一起。
- `metrics` 负责报表，方便用户核对结果。
- `nox` 负责整体路线判断，避免财务目标和其他目标冲突。

## 个人助手场景模板

适合个人事项、日程、提醒、整理信息、生成摘要等。

### 推荐写法

```json
{
  "title": "动作 + 对象 + 结果",
  "status": "INBOX",
  "assignee": "personal",
  "tags": ["daily", "personal"]
}
```

### 常见拆法

1. 先收集信息：让任务只负责“找齐材料”。
2. 再做整理：让任务只负责“形成结构”。
3. 最后输出建议：让任务只负责“给出可执行结论”。

### 适合的标题示例

- 整理今天下午的待办并按紧急程度排序
- 汇总本周邮件里待回复事项
- 把昨天的会议记录压缩成 3 条行动项
- 生成明天的出门准备清单

### 不推荐写法

- 帮我看看这个
- 处理一下我的事情
- 先想个方案

这类写法的问题是范围太大，Agent 很容易需要追问。

## 多 Agent 协作场景模板

适合分析、写作、运营、增长、报表、协作交接等。

### 推荐编排

把一个大目标拆成三层：

1. 数据层：`metrics` 负责收集和汇总。
2. 决策层：`nox` 或 `growth` 负责给出方向。
3. 表达层：`writing` 或 `email` 负责输出可读内容。

### 推荐任务格式

```json
{
  "title": "为本周增长复盘准备基础数据",
  "status": "INBOX",
  "assignee": "metrics",
  "tags": ["growth", "weekly", "data"]
}
```

```json
{
  "title": "基于数据给出增长策略建议",
  "status": "INBOX",
  "assignee": "growth",
  "tags": ["growth", "strategy"]
}
```

```json
{
  "title": "把策略建议整理成可发布总结",
  "status": "INBOX",
  "assignee": "writing",
  "tags": ["growth", "summary"]
}
```

### 适合的使用方式

- 先建一个总任务，明确目标。
- 再拆多个子任务，每个子任务只给一个 agent。
- 用评论记录交接，不要反复改任务标题。

### 评论模板

```json
{
  "author": "you",
  "body": "请优先输出结论，再给出 3 条可执行建议；如果数据不足，直接标注缺口。"
}
```

### 适合的标题示例

- 统计过去 7 天各 Agent 活跃度
- 归纳本周用户反馈的高频问题
- 把活动数据转成一页管理摘要
- 输出下周邮件营销草案

## 知识系统场景模板

适合资料导入、chunk、OCR、验证、召回、回流和审计。

### 推荐编排

把知识系统任务拆成四段：

1. 导入：把原始资料放进系统。
2. 处理：chunk 或 OCR 形成可检索单元。
3. 校验：确认数据是否可用、是否过期、是否被批准。
4. 召回与回流：检查结果并把反馈写回去。

### 推荐任务格式

```json
{
  "title": "导入本批原始资料并完成扫描",
  "status": "INBOX",
  "assignee": "nox",
  "tags": ["knowledge", "import"]
}
```

```json
{
  "title": "为扫描失败资料补做 OCR 或文本修复",
  "status": "INBOX",
  "assignee": "health",
  "tags": ["knowledge", "ocr", "repair"]
}
```

```json
{
  "title": "复核召回结果并确认可用于知识回流",
  "status": "INBOX",
  "assignee": "metrics",
  "tags": ["knowledge", "resolve", "audit"]
}
```

### 评论模板

```json
{
  "author": "you",
  "body": "这批资料优先保证可检索性，允许先粗后细；如果命中率低，请直接说明缺少哪类原始来源。"
}
```

### 适合的标题示例

- 导入新资料并生成初始知识单元
- 检查 OCR 失败样本并补充可读文本
- 复核 semantic resolve 结果是否偏离预期
- 标记已确认可用的知识单元

## 一套通用写法

如果你懒得想格式，可以直接套下面这个骨架：

```json
{
  "title": "动词 + 对象 + 结果",
  "status": "INBOX",
  "assignee": "nox",
  "tags": ["context-1", "context-2"]
}
```

再配一条评论：

```json
{
  "author": "you",
  "body": "请先给结论，再给依据；如果存在不确定性，请直接列出缺口。"
}
```

### 小脚本：一键创建任务

如果你经常要手动发任务，可以直接把下面这段保存成 `create-task.sh`，或者原样复制到终端执行。它会先加载本地 `mission-control.env`，再带着 `MC_AUTH_TOKEN` 调用任务接口，避免手动漏掉 Bearer token。

```bash
#!/usr/bin/env bash
set -euo pipefail

set -a
source panopticon/env/mission-control.env
set +a

: "${MC_AUTH_TOKEN:?set MC_AUTH_TOKEN first}"

curl -sS -X POST http://127.0.0.1:18910/v1/tasks \
  -H "Authorization: Bearer ${MC_AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "统计过去 7 天各 Agent 活跃度",
    "status": "INBOX",
    "assignee": "metrics",
    "tags": ["reporting", "panopticon"]
  }'
```

使用步骤很简单：

1. 确认你在仓库根目录。
2. 确认 `panopticon/env/mission-control.env` 里有可用的 `MC_AUTH_TOKEN`。
3. 运行这段脚本。

如果你想更稳一点，可以先用 `curl -i` 看返回体，再把 `-sS` 去掉；如果你只是想快速失败并返回结果，保留当前写法就够了。

## 实用原则

- 一个任务只表达一个结果。
- 一个任务只分配一个主责任人。
- 评论写上下文，标题写结果。
- 标签只做分类，不要承担整段说明。
- 大任务先拆小，再流转状态。

## 什么时候该拆任务

下面这些信号说明你该拆任务了：

- 一个标题里出现了“并且”“同时”“再”“然后”。
- 你发现同一个任务会同时找数据、写结论、再审校。
- 用户读完任务名仍然不知道完成后会得到什么。
- 同一任务需要不同 agent 轮流接手。

## 什么时候不用拆

- 目标很小，三句话能说清。
- 任务只需要一个 agent 一次性完成。
- 用户只需要一条结论，不需要过程管理。

## 最后建议

如果你是先给用户体验做优化，优先改三件事：

1. 让任务标题更像结果，不像请求。
2. 让每个 agent 的责任边界更清楚。
3. 让评论承担交接，而不是把所有信息塞进标题。
