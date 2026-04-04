# Knowledge Eval Skill

用于把 8-Agent 共用评估调用规范下沉成一个可复用的请求封装层。

核心目标：

- 统一构造 `POST /v1/knowledge/resolve` 请求
- 从环境变量自动补全 `agent_slug`、API 地址、token 和默认参数
- 对 `resolve` 响应输出统一摘要
- 避免 8 个 agent 各自重写客户端判断逻辑

## 目录

- `SKILL.md`：skill 入口说明
- `scripts/knowledge_eval.py`：请求封装与响应摘要实现
- `examples/*.json`：示例请求
- `tests/test_knowledge_eval.py`：单元测试

## 快速开始

```bash
cd panopticon/global-skills/knowledge-eval
python3 scripts/knowledge_eval.py \
  --task "评估当前交易策略是否适合执行" \
  --agent-slug trades \
  --risk-level high \
  --tags risk,position,market
```

## 环境变量

- `AGENT_SLUG`：默认 agent 标识
- `MISSION_CONTROL_API_URL`：Mission Control API base URL，例如 `http://localhost:18910`
- `KNOWLEDGE_RESOLVE_URL`：可直接指定完整 resolve URL，例如 `http://localhost:18910/v1/knowledge/resolve`
- `EVENT_HTTP_URL`：如果未单独配置 API URL，则尝试从事件上报地址推导 API base
- `EVENT_HTTP_TOKEN`：Bearer token
- `KNOWLEDGE_EVAL_DEFAULT_RISK`：默认风险等级，默认 `normal`
- `KNOWLEDGE_EVAL_DEFAULT_LIMIT`：默认返回条数，默认 `5`

## 返回结构

脚本输出 JSON，包含：

- `ok`：是否请求成功
- `request`：最终发送给后端的请求体
- `summary.status`：`ok | weak_hit | no_hit | rejected_only | service_error`
- `summary.top_items`：命中的核心资料摘要
- `summary.constraints`：限制与风险提示
- `summary.recommended_action`：建议动作
- `raw`：原始 resolve 响应

## 设计边界

- 不负责知识导入与 validation 写入
- 不替代后端 validation policy / ranking profile / audit
- 不默认混入 `/v1/knowledge/search` 编排

## 示例

- [examples/growth-experiment.json](examples/growth-experiment.json)
- [examples/trades-risk.json](examples/trades-risk.json)
- [examples/writing-brief.json](examples/writing-brief.json)