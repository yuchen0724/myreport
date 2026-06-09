---
name: semantic-layer-check
description: 语义层校验 — 在调用 LLM 能力前自动检查语义层文档，确保指标口径、维度、关联关系正确
user_invocable: false
disable_model_invocation: false
---

# 语义层校验

在涉及以下任一场景时，**必须先读取并校验语义层文档**：

- NL2SQL 自然语言转 SQL
- AI 分析师（ai-analyst）
- RCA 根因分析解读
- 语义指标查询
- 仪表盘生成
- 订阅推送生成
- 任何 prompt/SQL 生成链路变更

## 语义层文档路径

- 主指标口径定义: `semantic/semantic_layer.generated.json`
- 指标 schema: `semantic/semantic_layer.schema.yaml`
- 零售分析数据库: `semantic/零售分析数据库/retail_analysis.md`

## 校验清单

1. **指标口径**: 确认使用的指标与语义层中的口径一致（如「销售额」是否含税）
2. **维度层级**: 检查维度上下钻路径（如 区域→省份→城市）
3. **关联关系**: 验证多表 JOIN 条件是否正确
4. **时间范围**: 确认日期字段和过滤条件
5. **业务含义**: 确保 LLM 输出符合业务语义（不要混淆「订单数」和「订单行数」）

## 必须读 semantic/ 目录的场景

```
backend/app/api/nl2sql.py
backend/app/api/ai_analyst.py
backend/app/api/rca.py
backend/app/api/semantic_metric.py
backend/app/api/dashboard.py
backend/prompts/*
```
