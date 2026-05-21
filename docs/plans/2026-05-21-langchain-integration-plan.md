# LangChain 引入开发计划

## 背景

当前 NL2SQL 已经具备完整链路：语义层 prompt 构建、LLM 调用、JSON 解析、SQL 安全校验、SQL 修复、查询执行和图表推荐。LangChain 的引入目标不是替换业务流程，而是增强 LLM 适配、结构化输出和后续语义检索能力。

## 目标

1. 以低风险方式引入 LangChain，默认行为保持不变。
2. 保留 `LLMClient.chat(messages, temperature)` 作为业务层边界。
3. 支持通过配置在原始 HTTP 调用和 LangChain 调用之间切换。
4. 为后续结构化输出、语义层检索和 SQL 自动修复预留扩展点。

## 非目标

1. 不在第一阶段重写 `NL2SQLService` 主流程。
2. 不把 SQL 安全校验交给 LangChain。
3. 不在第一阶段引入 Agent 或 LangGraph。
4. 不改变前端和 API 响应结构。

## 当前现状

- `backend/requirements.txt` 已收敛到现代 LangChain 依赖组合，代码通过适配器开关启用 LangChain。
- `LLMClient` 当前使用自研 `httpx` 和 provider SDK 适配 OpenAI、Azure、Ollama、Anthropic。
- `NL2SQLService` 直接依赖 `LLMClient.chat()` 返回文本，再通过 `_parse_llm_response()` 解析 JSON。
- `SQLValidator` 是当前 SQL 安全边界，必须保留。
- `nl2sql_cache.py` 已存在，但尚未接入 NL2SQL 主流程。

## 分阶段计划

### 阶段 1：适配层接入

改动范围：

- `backend/app/config.py`
- `backend/app/utils/llm_client.py`
- `backend/.env.example`
- `backend/requirements.txt`
- `backend/tests/`

开发内容：

1. 新增配置 `LLM_ADAPTER=raw|langchain`，默认 `raw`。
2. 在 `LLMClient.chat()` 中按 adapter 分流。
3. 首期 LangChain 分支只支持 OpenAI-compatible chat completions。
4. LangChain 相关 import 使用延迟导入，依赖缺失时抛 `LLMError`。
5. 原始 `raw` 分支保持完全兼容，作为回滚路径。

验收标准：

- 不设置 `LLM_ADAPTER` 时行为不变。
- `LLM_ADAPTER=langchain` 时进入 LangChain 分支。
- 缺少 `langchain-openai` 时返回明确错误。
- API 测试不再 mock 不存在的 `generate_sql` 方法。

### 阶段 2：结构化输出

状态：已完成第一版。

开发内容：

1. 定义内部生成结果模型，包含 `sql`、`confidence`、`explanation`、`chart_config`。
2. 对支持结构化输出的模型优先使用 schema 约束。
3. 保留现有 `_parse_llm_response()` 作为兼容 fallback。

验收标准：

- 合法 JSON、markdown JSON block、纯文本异常均被覆盖。
- 非法输出仍会 fallback 到规则引擎。
- SQL 仍经过 `SQLValidator.validate()`。

实现说明：

- `GeneratedSQLResult` 和 `NL2SQLChartConfig` 作为内部结构化输出 schema。
- `LLMClient.chat_structured()` 仅在 `LLM_ADAPTER=langchain`、`LLM_PROVIDER=openai`、`LLM_API_MODE=chat` 时启用。
- `NL2SQLService` 会优先调用结构化输出，异常时回退到原始 `chat()` 文本 JSON 解析。

### 阶段 3：缓存与 Prompt 治理

状态：生成结果缓存和 Prompt builder 抽取已完成第一版。

开发内容：

1. 接入现有 `NL2SQLCache`。
2. cache key 纳入 `question`、`data_source_id`、`group_id`、语义文档版本。
3. 将长 system prompt 拆分为 builder 或模板文件。

验收标准：

- 相同问题命中缓存后不再调用 LLM。
- 数据源 schema 或语义文档变更后可失效缓存。
- Prompt 变更可追踪。

实现说明：

- 仅缓存 LLM 生成结果，不缓存最终查询结果。
- 缓存 key 包含 `question`、`data_source_id`、`group_id`、`context`、schema 指纹、LLM 指纹和 prompt 版本。
- 缓存命中后仍会进入后续 SQL 校验、SQL 修复和查询执行流程。
- 缓存载荷包含 `sql`、`confidence`、`explanation` 和 `chart_config`。
- NL2SQL system prompt 已从主流程中抽取到独立 builder，prompt 变更通过 `NL2SQL_PROMPT_VERSION` 显式管理缓存失效。

### 阶段 4：语义层检索与自动修 SQL

状态：语义层章节筛选和查询失败后的单次受控 SQL 自动修复已完成第一版。

开发内容：

1. 使用语义文档检索缩小 prompt 上下文。
2. 查询执行失败后，基于错误信息和相关 schema 进行一次受控修正。
3. 对修正次数、耗时和失败原因做可观测记录。

验收标准：

- 大语义文档场景 token 使用下降。
- 字段不存在、表名错误等常见失败可自动修正。
- 修正后的 SQL 仍通过安全校验。

实现说明：

- 仅在 LLM 生成 SQL 且首次查询执行失败时尝试一次自动修复。
- 修复 prompt 包含原始问题、失败 SQL、执行错误和当前 schema prompt。
- 修复 SQL 仍必须通过 `SQLValidator.validate()`，然后再走表名、聚合和日期字段修复。
- 修复执行仍失败时，保持原有失败响应，不影响主流程稳定性。
- 长 schema prompt 会按 markdown 章节做轻量关键词检索；短文本、未命中、压缩收益不明显或关闭开关时保持原文。
- 语义层检索配置项：`NL2SQL_SCHEMA_RETRIEVAL_ENABLED`、`NL2SQL_SCHEMA_RETRIEVAL_MIN_CHARS`、`NL2SQL_SCHEMA_RETRIEVAL_MAX_SECTIONS`。

## 回滚策略

默认配置：

```env
LLM_ADAPTER=raw
```

启用 LangChain：

```env
LLM_ADAPTER=langchain
```

如线上出现兼容性问题，只需将 `LLM_ADAPTER` 改回 `raw` 并重启服务。第一阶段不会移除原始调用链。

## 测试策略

1. 单元测试 `LLMClient` adapter 分流。
2. 单元测试 LangChain 依赖缺失错误。
3. 修正 NL2SQL API 测试，mock `chat()` 而不是不存在的 `generate_sql()`。
4. 聚焦执行：

```bash
rtk pytest backend/tests/test_llm_client.py backend/tests/test_query_api.py backend/tests/test_nl2sql.py -q
```

### 阶段 5：配置暴露与可观测性

状态：已完成第一版。

开发内容：

1. `/api/config` 返回 NL2SQL/LLM 运行时开关，便于前端和运维确认实际启用状态。
2. 不暴露 `LLM_API_KEY` 等敏感配置。
3. 前端 NL2SQL 配置日志输出 adapter、provider、model、结构化输出与 schema 检索状态。
4. 后端 schema 检索和 SQL 自动修复路径补充关键日志，便于排查是否压缩、是否修复、为何回退。

验收标准：

- 配置 API 可判断结构化输出是否实际启用。
- schema 检索关闭、短文档、未命中、收益不足、压缩成功都有明确日志。
- SQL 自动修复的安全校验和二次执行结果可追踪。
