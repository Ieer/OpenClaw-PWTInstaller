# infra.md (personal)

## Integrations

- 日历/任务/账单系统（按实际接入维护）

## Cron Jobs

### daily-finance-report
- **ID:** 31104a2a-9bbf-4b7b-ac5e-b55add897a65
- **时间:** 每天 08:00（Asia/Shanghai）
- **目标:** feishu direct chat
- **消息:** "生成今日消费统计：最近一月、本周一到今天、昨天的消费分析，包含合理性检查和开源节流建议"
- **管理命令:** `openclaw cron list`, `openclaw cron rm 31104a2a-9bbf-4b7b-ac5e-b55add897a65`

## Guardrails

- 不记录密钥/token 明文
- 不自动执行不可逆操作