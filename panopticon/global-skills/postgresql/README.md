# PostgreSQL Skill

安全只读 PostgreSQL 查询 Skill，适用于 AI Agent 的数据库问答场景。

## 快速开始

```bash
cd panopticon/global-skills/postgresql
pip install -r requirements.txt
python3 scripts/postgresql_skill.py --query "SELECT now() AS ts" --params "[]"
```

## 关键能力

- 只读 SQL 校验（SELECT/WITH）
- 屏蔽写入/DDL 关键字
- 参数化查询
- 自动追加 LIMIT（默认 1000）
- 统一 JSON 输出

## NL → SQL 模板映射

- 文件：`nl2sql_templates.json`
- 提供 20 条常见业务问句模板（如新增用户、GMV、转化率、留存、实验对比）
- 每条模板包含：
	- `question_examples`
	- `sql_template`（参数化）
	- `params_order`
	- `required_tables`

### 路由小工具

```bash
python3 scripts/nl2sql_router.py \
  --query "上周新注册用户有多少" \
  --top-k 3

# 严格按可用表集合过滤模板（生产推荐）
python3 scripts/nl2sql_router.py \
	--query "最近7天退款率" \
	--top-k 3 \
	--strict-allowlist "users,orders"
```

输出包含：
- 最匹配模板 `template_id`
- 置信分 `score`
- 参数顺序与参数提示（便于 AI/前端填参）
- 对应安全 SQL 模板
- 严格模式下被过滤模板数量与列表（`filtered_template_*`）

## 目录

- `SKILL.md`：Skill 入口说明
- `security.md`：安全设计与运维检查清单
- `scripts/postgresql_skill.py`：核心实现
- `scripts/nl2sql_router.py`：自然语言路由器（Top-K 模板匹配）
- `nl2sql_templates.json`：自然语言到安全 SQL 模板映射
- `examples/demo_readonly.py`：示例调用
- `tests/test_postgresql_skill.py`：单元测试
- `tests/test_nl2sql_router.py`：路由器单元测试
