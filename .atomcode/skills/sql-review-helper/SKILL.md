---
name: sql-review-helper
description: SQL 审核辅助 — 根据项目规范自动评审 SQL 模板、查询语句和方言适配
user_invocable: true
---

# SQL 审核辅助

当用户需要评审 SQL 语句、SQL 模板或需要进行 SQL 审核时，按以下流程进行。

## 项目 SQL 审核上下文

- SQL 模板存储在 `backend/app/api/templates.py`，通过 ParameterizedQuery 类管理参数化查询
- SQL 审核记录通过 `backend/app/api/sql_review.py` 管理
- 支持多个数据源（PostgreSQL、Doris、Hive），各数据源 SQL 方言有差异
- 配置在 `backend/app/models/data_source.py` 中
- LLM 提示词模板在 `backend/prompts/` 目录下

## 审核检查项

1. **SQL 注入防护**: 确保参数化查询而非字符串拼接
2. **性能风险**: 检查 WHERE 条件是否使用索引列、避免 SELECT *
3. **方言兼容性**: 确认 SQL 在目标数据源（Doris/Hive/PostgreSQL）中语法正确
4. **权限**: 确认用户有执行该查询的数据源权限
5. **超时风险**: 评估数据量和执行时间，建议添加 LIMIT/分页
6. **敏感数据**: 检查是否涉及敏感字段，需脱敏处理
7. **模板规范**: 检查 {{params}} 占位符是否正确，config JSON 格式是否合法

## 审核输出格式

```markdown
## SQL 审核报告

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 注入防护 | ✅/⚠️ | ... |
| 性能风险 | ✅/⚠️ | ... |
| 方言兼容 | ✅/⚠️ | ... |
| 权限检查 | ✅/⚠️ | ... |
| 超时风险 | ✅/⚠️ | ... |
| 敏感数据 | ✅/⚠️ | ... |
| 模板规范 | ✅/⚠️ | ... |

### 修改建议
- ...
```
