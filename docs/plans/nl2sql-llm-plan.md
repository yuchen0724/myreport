# NL2SQL LLM 增强实现计划

## 目标
将 NL2SQL 从规则引擎升级为 LLM 驱动，实现真正的自然语言到 SQL 转换。

## 任务列表

### 任务 1: 创建 LLM 客户端封装
**文件**: `backend/app/utils/llm_client.py`

**需求**:
- 支持多种 LLM 提供商: OpenAI, Azure OpenAI, Ollama, Anthropic
- 统一接口: `chat(messages, temperature, timeout)`
- 从配置文件读取 API 配置
- 错误处理和重试机制

**实现要点**:
```python
class LLMClient:
    def __init__(self, provider: str = "openai")
    def chat(self, messages: list, temperature: float = 0.0) -> str
    # 支持 provider: openai, azure, ollama, anthropic
```

### 任务 2: 扩展 Schema 描述生成逻辑
**文件**: `backend/app/services/nl2sql_service.py` (新增方法)

**需求**:
- 获取数据源的表结构（列名、类型、注释）
- 生成结构化的 schema 描述 prompt
- 包含主键、外键信息

**实现要点**:
```python
def build_schema_prompt(self, data_source_id: int) -> str:
    # 1. 获取数据源连接
    # 2. 查询表结构信息
    # 3. 生成 prompt 格式
```

### 任务 3: 重构 NL2SQL 服务集成 LLM
**文件**: `backend/app/services/nl2sql_service.py`

**需求**:
- 重写 `parse_question` 方法使用 LLM
- 构建系统提示词（包含 schema）
- 构建用户提示词（问题）
- 解析 LLM 返回的 JSON
- SQL 校验和安全检查
- 保留规则引擎作为 fallback

**实现要点**:
```python
def parse_question(self, request: NL2SQLRequest, user_id: int) -> NL2SQLResponse:
    # 1. 构建 schema prompt
    # 2. 调用 LLM 生成 SQL
    # 3. 解析 JSON 响应
    # 4. 验证 SQL 安全性
    # 5. 执行查询
```

### 任务 4: 添加多模型支持配置
**文件**: `backend/app/config.py`

**需求**:
- 添加 LLM_PROVIDER 配置
- 添加各 provider 特有配置
- 添加 NL2SQL 行为配置

**实现要点**:
```python
# .env 配置
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-3.5-turbo
# Azure
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-35-turbo
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
# NL2SQL 行为
NL2SQL_TEMPERATURE=0.0
NL2SQL_MAX_RETRIES=2
NL2SQL_TIMEOUT=30
```

### 任务 5: 添加 Redis 缓存层
**文件**: `backend/app/utils/nl2sql_cache.py` (新增)

**需求**:
- 缓存相同问题的 SQL 生成结果
- 使用问题文本 hash 作为 key
- TTL 可配置

**实现要点**:
```python
class NL2SQLCache:
    def get(self, question_hash: str) -> Optional[str]
    def set(self, question_hash: str, sql: str, ttl: int = 3600)
    def invalidate(self, data_source_id: int)
```

### 任务 6: 测试验证 NL2SQL 功能
**文件**: 测试脚本

**需求**:
- 测试简单查询转换
- 测试复杂查询转换
- 测试 fallback 机制
- 测试缓存机制

## 验收标准
- [ ] 支持多种 LLM 提供商
- [ ] 能够根据表结构生成正确 SQL
- [ ] SQL 执行安全（禁止 UPDATE/DELETE/DROP）
- [ ] 缓存机制正常工作
- [ ] 规则引擎 fallback 正常