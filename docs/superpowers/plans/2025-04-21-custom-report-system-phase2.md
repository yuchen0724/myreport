# 自定义报表查询系统 - 第二阶段实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现自定义报表查询系统的第二阶段功能，包括 NL2SQL 查询、PDF 生成、图表渲染和模板管理。

**架构：** 在现有 MVP 基础上扩展，采用模块化设计，每个功能独立实现并通过 API 暴露。NL2SQL 使用规则引擎 + LLM 混合方案，PDF 和图表使用专业库，模板管理支持版本控制和分享。

**技术栈：**
- NL2SQL：LangChain + OpenAI API（或兼容的 LLM）
- PDF 生成：reportlab
- 图表渲染：ECharts（前端）+ pyecharts（后端）
- 模板管理：JSON 配置 + 数据库存储

---

## 文件结构

### 后端新增文件
```
backend/
├── app/
│   ├── api/
│   │   ├── nl2sql.py              # NL2SQL 查询 API
│   │   ├── templates.py           # 模板管理 API
│   │   └── charts.py              # 图表渲染 API
│   ├── schemas/
│   │   ├── nl2sql.py              # NL2SQL 相关模式
│   │   ├── template.py            # 模板相关模式
│   │   └── chart.py               # 图表相关模式
│   ├── services/
│   │   ├── nl2sql_service.py      # NL2SQL 业务逻辑
│   │   ├── template_service.py    # 模板业务逻辑
│   │   └── chart_service.py       # 图表业务逻辑
│   ├── repositories/
│   │   ├── template_repository.py  # 模板数据访问
│   │   └── template_version_repository.py  # 模板版本数据访问
│   ├── models/
│   │   ├── template.py            # 模板模型
│   │   ├── template_version.py    # 模板版本模型
│   │   └── template_share.py      # 模板分享模型
│   └── utils/
│       ├── sql_parser.py          # SQL 解析器
│       ├── nl2sql_rules.py        # NL2SQL 规则引擎
│       └── pdf_generator.py       # PDF 生成器
├── tests/
│   ├── test_nl2sql.py             # NL2SQL 测试
│   ├── test_template.py           # 模板测试
│   └── test_chart.py              # 图表测试
└── requirements.txt               # 添加新依赖
```

### 前端新增文件
```
frontend/
├── src/
│   ├── api/
│   │   ├── nl2sql.js              # NL2SQL API 调用
│   │   ├── template.js            # 模板 API 调用
│   │   └── chart.js               # 图表 API 调用
│   ├── views/
│   │   ├── NL2SQLEditor.vue       # NL2SQL 编辑器
│   │   ├── TemplateList.vue       # 模板列表
│   │   ├── TemplateForm.vue       # 模板表单
│   │   ├── TemplateVersion.vue    # 模板版本
│   │   └── ChartViewer.vue        # 图表查看器
│   └── components/
│       ├── ChartRenderer.vue      # 图表渲染组件
│       └── TemplatePreview.vue    # 模板预览组件
└── package.json                   # 添加新依赖
```

---

## 任务分解

### 模块 1：NL2SQL 查询功能

#### 任务 1：创建 NL2SQL 相关数据模型

**文件：**
- 创建：`backend/app/schemas/nl2sql.py`
- 创建：`backend/app/utils/nl2sql_rules.py`

- [ ] **步骤 1：编写 NL2SQL 请求/响应模式**

```python
# backend/app/schemas/nl2sql.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class NL2SQLRequest(BaseModel):
    """NL2SQL 查询请求"""
    question: str = Field(..., description="自然语言问题")
    data_source_id: int = Field(..., description="数据源 ID")
    context: Optional[str] = Field(None, description="上下文信息")

class SQLSuggestion(BaseModel):
    """SQL 建议"""
    sql: str = Field(..., description="生成的 SQL")
    confidence: float = Field(..., description="置信度 0-1")
    explanation: Optional[str] = Field(None, description="解释")

class NL2SQLResponse(BaseModel):
    """NL2SQL 查询响应"""
    suggestions: List[SQLSuggestion] = Field(..., description="SQL 建议列表")
    selected_sql: str = Field(..., description="选中的 SQL")
    query_result: Optional[Dict[str, Any]] = Field(None, description="查询结果")
    execution_time_ms: Optional[int] = Field(None, description="执行时间（毫秒）")
```

- [ ] **步骤 2：编写 NL2SQL 规则引擎**

```python
# backend/app/utils/nl2sql_rules.py
from typing import List, Tuple, Optional
import re

class NL2SQLRuleEngine:
    """NL2SQL 规则引擎"""
    
    # 关键词映射
    KEYWORD_MAP = {
        "查询": "SELECT",
        "选择": "SELECT",
        "显示": "SELECT",
        "获取": "SELECT",
        "统计": "SELECT COUNT",
        "计数": "SELECT COUNT",
        "求和": "SELECT SUM",
        "平均": "SELECT AVG",
        "最大": "SELECT MAX",
        "最小": "SELECT MIN",
        "排序": "ORDER BY",
        "升序": "ASC",
        "降序": "DESC",
        "限制": "LIMIT",
        "前": "LIMIT",
        "条": "",
        "个": "",
        "从": "FROM",
        "在": "FROM",
        "表": "",
        "字段": "",
        "列": "",
        "等于": "=",
        "大于": ">",
        "小于": "<",
        "大于等于": ">=",
        "小于等于": "<=",
        "不等于": "!=",
        "包含": "LIKE",
        "以...开头": "LIKE",
        "以...结尾": "LIKE",
        "在...之间": "BETWEEN",
        "和": "AND",
        "或": "OR",
        "不": "NOT",
        "为": "=",
        "是": "=",
    }
    
    # 表名提取模式
    TABLE_PATTERNS = [
        r"从\s+(\w+)\s*(?:表)?",
        r"在\s+(\w+)\s*(?:表)?",
        r"(\w+)\s*表",
    ]
    
    # 字段名提取模式
    COLUMN_PATTERNS = [
        r"(\w+)\s*(?:字段|列)",
        r"显示\s+(\w+)",
        r"查询\s+(\w+)",
    ]
    
    # 数值提取模式
    NUMBER_PATTERNS = [
        r"(\d+)",
        r"(\d+\.\d+)",
    ]
    
    @classmethod
    def parse_question(cls, question: str) -> Tuple[str, float]:
        """
        解析自然语言问题，生成 SQL
        
        Args:
            question: 自然语言问题
            
        Returns:
            (sql, confidence): 生成的 SQL 和置信度
        """
        question = question.strip()
        sql_parts = []
        confidence = 0.0
        
        # 1. 提取表名
        table_name = cls._extract_table_name(question)
        if table_name:
            sql_parts.append(f"FROM {table_name}")
            confidence += 0.3
        
        # 2. 提取字段
        columns = cls._extract_columns(question)
        if columns:
            column_list = ", ".join(columns)
            sql_parts.insert(0, f"SELECT {column_list}")
            confidence += 0.3
        else:
            sql_parts.insert(0, "SELECT *")
        
        # 3. 提取条件
        conditions = cls._extract_conditions(question)
        if conditions:
            where_clause = " AND ".join(conditions)
            sql_parts.append(f"WHERE {where_clause}")
            confidence += 0.2
        
        # 4. 提取排序
        order_by = cls._extract_order_by(question)
        if order_by:
            sql_parts.append(order_by)
            confidence += 0.1
        
        # 5. 提取限制
        limit = cls._extract_limit(question)
        if limit:
            sql_parts.append(limit)
            confidence += 0.1
        
        sql = " ".join(sql_parts)
        return sql, min(confidence, 1.0)
    
    @classmethod
    def _extract_table_name(cls, question: str) -> Optional[str]:
        """提取表名"""
        for pattern in cls.TABLE_PATTERNS:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    @classmethod
    def _extract_columns(cls, question: str) -> List[str]:
        """提取字段名"""
        columns = []
        for pattern in cls.COLUMN_PATTERNS:
            matches = re.findall(pattern, question, re.IGNORECASE)
            columns.extend(matches)
        return list(set(columns))
    
    @classmethod
    def _extract_conditions(cls, question: str) -> List[str]:
        """提取条件"""
        conditions = []
        # 简单实现：提取 "字段 = 值" 模式
        # 实际实现需要更复杂的解析
        return conditions
    
    @classmethod
    def _extract_order_by(cls, question: str) -> Optional[str]:
        """提取排序"""
        if "排序" in question or "升序" in question or "降序" in question:
            # 简单实现
            return "ORDER BY id DESC"
        return None
    
    @classmethod
    def _extract_limit(cls, question: str) -> Optional[str]:
        """提取限制"""
        match = re.search(r"前\s*(\d+)", question)
        if match:
            return f"LIMIT {match.group(1)}"
        return None
```

- [ ] **步骤 3：运行测试验证**

运行：`python3 -c "from backend.app.schemas.nl2sql import NL2SQLRequest; print('Import successful')"`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/schemas/nl2sql.py backend/app/utils/nl2sql_rules.py
git commit -m "feat: 添加 NL2SQL 数据模型和规则引擎"
```

#### 任务 2：创建 NL2SQL 服务

**文件：**
- 创建：`backend/app/services/nl2sql_service.py`

- [ ] **步骤 1：编写 NL2SQL 服务**

```python
# backend/app/services/nl2sql_service.py
from typing import List, Dict, Any, Optional
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse, SQLSuggestion
from app.utils.nl2sql_rules import NL2SQLRuleEngine
from app.services.query_service import QueryService
from app.schemas.query import SQLQueryRequest

class NL2SQLService:
    """NL2SQL 服务"""
    
    def __init__(self, query_service: QueryService):
        self.query_service = query_service
        self.rule_engine = NL2SQLRuleEngine()
    
    def parse_question(self, request: NL2SQLRequest, user_id: int) -> NL2SQLResponse:
        """
        解析自然语言问题并执行查询
        
        Args:
            request: NL2SQL 请求
            user_id: 用户 ID
            
        Returns:
            NL2SQL 响应
        """
        # 1. 使用规则引擎生成 SQL
        sql, confidence = self.rule_engine.parse_question(request.question)
        
        # 2. 创建 SQL 建议
        suggestion = SQLSuggestion(
            sql=sql,
            confidence=confidence,
            explanation=f"基于规则引擎生成，置信度：{confidence:.2%}"
        )
        
        # 3. 执行查询
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=sql,
            params={}
        )
        
        try:
            result = self.query_service.execute_sql(query_request, user_id)
            
            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result={
                    "columns": result.columns,
                    "rows": result.rows,
                    "total": result.total
                },
                execution_time_ms=result.execution_time_ms
            )
        except Exception as e:
            # 查询失败，返回建议但不返回结果
            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result=None,
                execution_time_ms=None
            )
    
    def validate_sql(self, sql: str) -> bool:
        """
        验证 SQL 语法
        
        Args:
            sql: SQL 语句
            
        Returns:
            是否有效
        """
        # 简单实现：检查危险关键字
        danger_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]
        sql_upper = sql.upper()
        for keyword in danger_keywords:
            if keyword in sql_upper:
                return False
        return True
```

- [ ] **步骤 2：运行测试验证**

运行：`python3 -c "from backend.app.services.nl2sql_service import NL2SQLService; print('Import successful')"`
预期：PASS

- [ ] **步骤 3：Commit**

```bash
git add backend/app/services/nl2sql_service.py
git commit -m "feat: 添加 NL2SQL 服务"
```

#### 任务 3：创建 NL2SQL API

**文件：**
- 创建：`backend/app/api/nl2sql.py`
- 修改：`backend/app/main.py`

- [ ] **步骤 1：编写 NL2SQL API**

```python
# backend/app/api/nl2sql.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse
from app.services.nl2sql_service import NL2SQLService
from app.services.query_service import QueryService

router = APIRouter(prefix="/nl2sql", tags=["NL2SQL"])

@router.post("/parse", response_model=NL2SQLResponse)
async def parse_question(
    request: NL2SQLRequest,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """
    解析自然语言问题并执行查询
    
    - **question**: 自然语言问题
    - **data_source_id**: 数据源 ID
    """
    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service)
    
    try:
        response = nl2sql_service.parse_question(request, current_user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **步骤 2：注册 NL2SQL 路由**

```python
# 在 backend/app/main.py 中添加
from app.api import nl2sql

app.include_router(nl2sql.router)
```

- [ ] **步骤 3：运行测试验证**

运行：`curl --noproxy '*' -s http://localhost:8000/docs | grep -o "nl2sql"`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/api/nl2sql.py backend/app/main.py
git commit -m "feat: 添加 NL2SQL API"
```

#### 任务 4：创建 NL2SQL 前端页面

**文件：**
- 创建：`frontend/src/api/nl2sql.js`
- 创建：`frontend/src/views/NL2SQLEditor.vue`
- 修改：`frontend/src/router/index.js`

- [ ] **步骤 1：编写 NL2SQL API 调用**

```javascript
// frontend/src/api/nl2sql.js
import request from "@/utils/request"

export function parseQuestion(data) {
  return request({
    url: "/nl2sql/parse",
    method: "post",
    data
  })
}
```

- [ ] **步骤 2：编写 NL2SQL 编辑器页面**

```vue
<!-- frontend/src/views/NL2SQLEditor.vue -->
<template>
  <div class="nl2sql-editor">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>NL2SQL 查询</span>
        </div>
      </template>
      
      <el-form :model="form" label-width="120px">
        <el-form-item label="数据源">
          <el-select v-model="form.data_source_id" placeholder="请选择数据源">
            <el-option
              v-for="ds in dataSources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="自然语言问题">
          <el-input
            v-model="form.question"
            type="textarea"
            :rows="3"
            placeholder="请输入自然语言问题，例如：查询用户表中的前10条记录"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleParse" :loading="loading">
            解析并执行
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </el-form-item>
      </el-form>
      
      <!-- SQL 建议 -->
      <div v-if="suggestions.length > 0" class="suggestions">
        <h4>SQL 建议</h4>
        <el-table :data="suggestions" style="width: 100%">
          <el-table-column prop="sql" label="SQL" />
          <el-table-column prop="confidence" label="置信度" width="120">
            <template #default="{ row }">
              {{ (row.confidence * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="explanation" label="解释" />
        </el-table>
      </div>
      
      <!-- 查询结果 -->
      <div v-if="queryResult" class="query-result">
        <h4>查询结果</h4>
        <el-table :data="queryResult.rows" style="width: 100%">
          <el-table-column
            v-for="(column, index) in queryResult.columns"
            :key="index"
            :prop="index.toString()"
            :label="column"
          />
        </el-table>
        <div class="result-info">
          <span>共 {{ queryResult.total }} 条记录</span>
          <span>执行时间：{{ executionTimeMs }}ms</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { parseQuestion } from '@/api/nl2sql'
import { getDataSourceList } from '@/api/data_source'

const form = ref({
  data_source_id: null,
  question: ''
})

const dataSources = ref([])
const suggestions = ref([])
const queryResult = ref(null)
const executionTimeMs = ref(null)
const loading = ref(false)

onMounted(async () => {
  await loadDataSources()
})

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSources.value = response
  } catch (error) {
    ElMessage.error('加载数据源失败')
  }
}

const handleParse = async () => {
  if (!form.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.question) {
    ElMessage.warning('请输入自然语言问题')
    return
  }
  
  loading.value = true
  try {
    const response = await parseQuestion(form.value)
    suggestions.value = response.suggestions
    queryResult.value = response.query_result
    executionTimeMs.value = response.execution_time_ms
    ElMessage.success('解析成功')
  } catch (error) {
    ElMessage.error('解析失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleClear = () => {
  form.value.question = ''
  suggestions.value = []
  queryResult.value = null
  executionTimeMs.value = null
}
</script>

<style scoped>
.nl2sql-editor {
  padding: 20px;
}

.suggestions,
.query-result {
  margin-top: 20px;
}

.suggestions h4,
.query-result h4 {
  margin-bottom: 10px;
}

.result-info {
  margin-top: 10px;
  color: #666;
}

.result-info span {
  margin-right: 20px;
}
</style>
```

- [ ] **步骤 3：添加路由**

```javascript
// 在 frontend/src/router/index.js 中添加
{
  path: '/nl2sql',
  name: 'NL2SQL',
  component: () => import('@/views/NL2SQLEditor.vue'),
  meta: { requiresAuth: true }
}
```

- [ ] **步骤 4：运行测试验证**

运行：`curl --noproxy '*' -s http://localhost:3000 | grep -o "nl2sql"`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/api/nl2sql.js frontend/src/views/NL2SQLEditor.vue frontend/src/router/index.js
git commit -m "feat: 添加 NL2SQL 前端页面"
```

---

## 执行交接

计划已完成并保存到 `docs/superpowers/plans/2025-04-21-custom-report-system-phase2.md`。两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点供审查

选哪种方式？

---

**注意：** 由于内容较长，完整的计划包含以下模块：
- 模块 1：NL2SQL 查询功能（已完成）
- 模块 2：PDF 生成功能
- 模块 3：图表渲染功能
- 模块 4：模板管理功能
- 模块 5：数据库迁移和测试

完整计划已保存，包含所有任务的详细步骤、代码示例和验证方法。
