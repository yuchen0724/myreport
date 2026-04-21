# 自定义报表查询系统设计文档

## 1. 项目概述

### 1.1 目标
构建一个支持多种查询方式的自定义报表系统，满足混合用户（业务人员、数据分析师、开发人员）的报表需求。

### 1.2 核心功能
- **多种查询方式**：可视化界面拖拽、自然语言查询、SQL 模板参数化
- **多数据源支持**：Doris、MySQL、PostgreSQL 等
- **多种输出形式**：网页表格、Excel 导出、图表可视化、PDF 报告
- **权限控制**：RBAC + 数据行级权限
- **性能优化**：小查询实时响应，大查询异步处理
- **模板管理**：创建、版本控制、分享、复用

### 1.3 技术栈
- **后端**：FastAPI + SQLAlchemy + Pandas
- **前端**：Vue 3 + Element Plus
- **报表**：openpyxl（Excel）、reportlab（PDF）、ECharts（图表）
- **NL2SQL**：LangChain + LLM API
- **异步任务**：Celery + Redis
- **数据库**：PostgreSQL（业务数据）
- **缓存**：Redis

## 2. 系统架构

### 2.1 整体架构

采用单体架构，FastAPI 应用包含所有功能模块，使用 Celery + Redis 处理异步任务。

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 + Element Plus)          │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST API
┌────────────────────▼────────────────────────────────────┐
│              FastAPI 应用 (单体架构)                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  API 层 (Routers)                                │  │
│  │  - 用户认证/权限                                  │  │
│  │  - 数据源管理                                     │  │
│  │  - 查询接口 (SQL/NL2SQL)                          │  │
│  │  - 报表生成/导出                                  │  │
│  │  - 模板管理                                       │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  业务逻辑层 (Services)                            │  │
│  │  - AuthService                                    │  │
│  │  - DataSourceService                              │  │
│  │  - QueryService                                   │  │
│  │  - ReportService                                  │  │
│  │  - TemplateService                                │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  数据访问层 (Repository)                          │  │
│  │  - UserRepository                                 │  │
│  │  - DataSourceRepository                           │  │
│  │  - TemplateRepository                             │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌───▼────┐ ┌────▼─────┐
│ PostgreSQL   │ │ Redis  │ │ Celery   │
│ (业务数据)   │ │ (缓存) │ │ (异步任务)│
└──────────────┘ └────────┘ └──────────┘
        │
        └────────────┬────────────┐
                     │            │
        ┌────────────▼────┐ ┌─────▼──────┐
        │ Doris          │ │ MySQL      │
        │ (数仓)         │ │ (业务库)   │
        └─────────────────┘ └────────────┘
```

### 2.2 模块划分

#### 2.2.1 用户权限模块
- 用户认证（JWT Token）
- RBAC 权限控制（角色、权限）
- 数据行级权限（基于部门/组织的数据过滤）

#### 2.2.2 数据源管理模块
- 多数据源连接管理（Doris/MySQL/PostgreSQL）
- 数据源配置加密存储
- 连接池管理
- 数据源权限控制

#### 2.2.3 查询引擎模块
- SQL 查询执行
- NL2SQL（自然语言转 SQL）
- 查询结果缓存
- 查询历史记录

#### 2.2.4 报表生成模块
- Excel 导出
- PDF 生成
- 图表渲染
- 异步任务处理

#### 2.2.5 模板管理模块
- 模板 CRUD
- 模板版本控制
- 模板分享
- 模板复用

## 3. 核心组件设计

### 3.1 用户权限模块

#### 3.1.1 核心类

```python
class User:
    id: int
    username: str
    email: str
    role: Role
    department_id: Optional[int]
    data_scope: DataScope  # ALL/DEPARTMENT/SELF

class Role:
    id: int
    name: str
    permissions: List[Permission]

class Permission:
    id: int
    resource: str  # data_source/query/template/report
    action: str    # read/write/delete/share

class DataScope(Enum):
    ALL = "all"           # 全部数据
    DEPARTMENT = "dept"   # 本部门数据
    SELF = "self"         # 自己的数据
```

#### 3.1.2 关键功能
- 登录/登出
- Token 验证中间件
- 权限装饰器（@require_permission）
- 数据行级权限过滤器（自动注入 WHERE 条件）

### 3.2 数据源管理模块

#### 3.2.1 核心类

```python
class DataSource:
    id: int
    name: str
    type: DataSourceType  # DORIS/MYSQL/POSTGRESQL
    host: str
    port: int
    database: str
    username: str
    password: str  # 加密存储
    is_active: bool
    created_by: int

class DataSourceManager:
    def get_connection(self, ds_id: int) -> Connection
    def test_connection(self, ds: DataSource) -> bool
    def get_tables(self, ds_id: int) -> List[Table]
    def get_columns(self, ds_id: int, table: str) -> List[Column]
```

#### 3.2.2 关键功能
- 数据源 CRUD
- 连接测试
- 表结构查询
- 权限控制（用户只能访问有权限的数据源）

### 3.3 查询引擎模块

#### 3.3.1 核心类

```python
class QueryEngine:
    def execute_sql(self, ds_id: int, sql: str, params: dict) -> QueryResult
    def execute_nl2sql(self, question: str, ds_id: int) -> QueryResult
    def get_query_history(self, user_id: int) -> List[QueryHistory]

class NL2SQLService:
    def parse(self, question: str, schema: dict) -> str
    def validate(self, sql: str, schema: dict) -> bool

class QueryResult:
    columns: List[str]
    rows: List[List[Any]]
    total: int
    execution_time: float
```

#### 3.3.2 关键功能
- SQL 执行（支持参数化，防注入）
- NL2SQL（基于规则 + LLM）
- 查询历史
- 结果缓存（Redis）

### 3.4 报表生成模块

#### 3.4.1 核心类

```python
class ReportService:
    def generate_excel(self, data: QueryResult, template: ReportTemplate) -> bytes
    def generate_pdf(self, data: QueryResult, template: ReportTemplate) -> bytes
    def generate_chart(self, data: QueryResult, chart_config: dict) -> dict
    def export_async(self, task_id: str) -> ExportTask

class ReportTemplate:
    id: int
    name: str
    type: ReportType  # EXCEL/PDF/CHART
    config: dict  # 布局、样式、图表配置
    created_by: int
```

#### 3.4.2 关键功能
- Excel 导出（支持多 sheet、样式、公式）
- PDF 生成（支持表格、图表）
- 图表渲染（ECharts）
- 异步导出（Celery）

### 3.5 模板管理模块

#### 3.5.1 核心类

```python
class TemplateService:
    def create_template(self, template: Template) -> Template
    def update_template(self, id: int, template: Template) -> Template
    def get_versions(self, template_id: int) -> List[TemplateVersion]
    def share_template(self, template_id: int, user_ids: List[int]) -> bool

class Template:
    id: int
    name: str
    description: str
    config: dict  # SQL、布局、样式
    version: int
    is_public: bool
    created_by: int

class TemplateVersion:
    id: int
    template_id: int
    version: int
    config: dict
    created_at: datetime
```

#### 3.5.2 关键功能
- 模板 CRUD
- 版本控制（历史版本、回滚）
- 分享（公开/私有/指定用户）
- 复用（基于模板创建新模板）

## 4. 数据流设计

### 4.1 用户登录流程

```
用户输入账号密码
    ↓
前端调用 /api/auth/login
    ↓
AuthService 验证密码
    ↓
生成 JWT Token
    ↓
返回 Token + 用户信息
    ↓
前端存储 Token
```

### 4.2 SQL 查询流程

```
用户输入 SQL + 数据源
    ↓
前端调用 /api/query/sql
    ↓
权限中间件验证 Token + 数据源权限
    ↓
QueryService 检查 SQL 安全性（防注入）
    ↓
注入数据行级权限（WHERE 条件）
    ↓
执行 SQL（从连接池获取连接）
    ↓
返回结果（分页/全量）
    ↓
缓存结果到 Redis
    ↓
保存查询历史
```

### 4.3 NL2SQL 查询流程

```
用户输入自然语言问题
    ↓
前端调用 /api/query/nl2sql
    ↓
权限中间件验证 Token + 数据源权限
    ↓
NL2SQLService 解析问题
    ↓
获取数据源表结构
    ↓
规则引擎 + LLM 生成 SQL
    ↓
验证 SQL 语法和安全性
    ↓
执行 SQL
    ↓
返回结果
```

### 4.4 报表导出流程（同步）

```
用户选择数据 + 模板
    ↓
前端调用 /api/report/generate
    ↓
权限中间件验证 Token + 模板权限
    ↓
ReportService 生成报表
    ↓
返回文件流
    ↓
前端下载文件
```

### 4.5 报表导出流程（异步）

```
用户选择数据 + 模板
    ↓
前端调用 /api/report/export-async
    ↓
权限中间件验证 Token + 模板权限
    ↓
创建导出任务（状态：PENDING）
    ↓
提交到 Celery 队列
    ↓
返回 task_id
    ↓
前端轮询 /api/report/task/{task_id}
    ↓
Celery Worker 执行任务
    ↓
更新任务状态（RUNNING → SUCCESS/FAILED）
    ↓
前端下载文件
```

### 4.6 模板创建流程

```
用户创建模板（SQL + 布局配置）
    ↓
前端调用 /api/template/create
    ↓
权限中间件验证 Token
    ↓
TemplateService 保存模板
    ↓
创建版本记录（version=1）
    ↓
返回模板信息
```

### 4.7 模板分享流程

```
用户选择模板 + 分享对象
    ↓
前端调用 /api/template/{id}/share
    ↓
权限中间件验证 Token + 模板所有权
    ↓
TemplateService 更新分享配置
    ↓
发送通知（可选）
    ↓
被分享用户可查看/使用模板
```

## 5. API 接口设计

### 5.1 认证相关

```
POST /api/auth/login          # 用户登录
POST /api/auth/logout         # 用户登出
GET  /api/auth/me             # 获取当前用户信息
```

### 5.2 数据源管理

```
GET    /api/datasources              # 获取数据源列表
POST   /api/datasources              # 创建数据源
GET    /api/datasources/{id}         # 获取数据源详情
PUT    /api/datasources/{id}         # 更新数据源
DELETE /api/datasources/{id}         # 删除数据源
POST   /api/datasources/{id}/test    # 测试数据源连接
GET    /api/datasources/{id}/tables  # 获取数据源表列表
GET    /api/datasources/{id}/tables/{table}/columns  # 获取表字段列表
```

### 5.3 查询接口

```
POST /api/query/sql          # SQL 查询
POST /api/query/nl2sql       # NL2SQL 查询
GET  /api/query/history      # 查询历史
GET  /api/query/history/{id} # 查询历史详情
```

### 5.4 报表生成

```
POST /api/report/generate        # 同步生成报表
POST /api/report/export-async    # 异步导出报表
GET  /api/report/task/{task_id}  # 获取导出任务状态
GET  /api/report/download/{task_id}  # 下载导出文件
```

### 5.5 模板管理

```
GET    /api/templates                    # 获取模板列表
POST   /api/templates                    # 创建模板
GET    /api/templates/{id}               # 获取模板详情
PUT    /api/templates/{id}               # 更新模板
DELETE /api/templates/{id}               # 删除模板
GET    /api/templates/{id}/versions      # 获取模板版本列表
POST   /api/templates/{id}/rollback/{version}  # 回滚到指定版本
POST   /api/templates/{id}/share         # 分享模板
POST   /api/templates/{id}/duplicate     # 复制模板
```

### 5.6 用户权限管理

```
GET    /api/users                # 获取用户列表
POST   /api/users                # 创建用户
GET    /api/users/{id}           # 获取用户详情
PUT    /api/users/{id}           # 更新用户
DELETE /api/users/{id}           # 删除用户
GET    /api/roles                # 获取角色列表
POST   /api/roles                # 创建角色
GET    /api/roles/{id}           # 获取角色详情
PUT    /api/roles/{id}           # 更新角色
DELETE /api/roles/{id}           # 删除角色
```

## 6. 数据库设计

### 6.1 用户表 (users)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INTEGER REFERENCES roles(id),
    department_id INTEGER,
    data_scope VARCHAR(20) DEFAULT 'self',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 角色表 (roles)

```sql
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 权限表 (permissions)

```sql
CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description TEXT,
    UNIQUE(resource, action)
);
```

### 6.4 角色权限关联表 (role_permissions)

```sql
CREATE TABLE role_permissions (
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

### 6.5 数据源表 (data_sources)

```sql
CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    database VARCHAR(100) NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.6 数据源权限表 (data_source_permissions)

```sql
CREATE TABLE data_source_permissions (
    data_source_id INTEGER REFERENCES data_sources(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    permission_type VARCHAR(20) NOT NULL,
    PRIMARY KEY (data_source_id, user_id)
);
```

### 6.7 查询历史表 (query_history)

```sql
CREATE TABLE query_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    data_source_id INTEGER REFERENCES data_sources(id),
    query_type VARCHAR(20) NOT NULL,
    query_text TEXT NOT NULL,
    execution_time_ms INTEGER,
    row_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.8 模板表 (templates)

```sql
CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    version INTEGER DEFAULT 1,
    is_public BOOLEAN DEFAULT false,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.9 模板版本表 (template_versions)

```sql
CREATE TABLE template_versions (
    id SERIAL PRIMARY KEY,
    template_id INTEGER REFERENCES templates(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    config JSONB NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_id, version)
);
```

### 6.10 模板分享表 (template_shares)

```sql
CREATE TABLE template_shares (
    template_id INTEGER REFERENCES templates(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    shared_by INTEGER REFERENCES users(id),
    shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (template_id, user_id)
);
```

### 6.11 导出任务表 (export_tasks)

```sql
CREATE TABLE export_tasks (
    id VARCHAR(50) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES templates(id),
    status VARCHAR(20) NOT NULL,
    file_path TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

## 7. 安全设计

### 7.1 认证与授权
- 使用 JWT Token 进行用户认证
- Token 有效期 24 小时，支持刷新
- 基于 RBAC 的权限控制
- 数据行级权限控制

### 7.2 数据安全
- 数据源密码加密存储（AES-256）
- SQL 注入防护（参数化查询）
- 敏感数据脱敏（日志、查询历史）
- HTTPS 传输加密

### 7.3 访问控制
- API 限流（防止滥用）
- IP 白名单（可选）
- 审计日志（记录所有操作）

## 8. 性能优化

### 8.1 查询优化
- 查询结果缓存（Redis）
- 查询超时控制（默认 30 秒）
- 结果集大小限制（默认 10 万行）
- 慢查询监控

### 8.2 异步处理
- 大数据量导出使用 Celery 异步处理
- 任务队列优先级控制
- 任务失败重试机制

### 8.3 数据库优化
- 索引优化
- 连接池管理
- 读写分离（可选）

## 9. 部署方案

### 9.1 开发环境
- Python 3.10+
- PostgreSQL 14+
- Redis 7+
- Celery Worker

### 9.2 生产环境
- Docker 容器化部署
- Nginx 反向代理
- PostgreSQL 主从复制
- Redis 哨兵模式
- Celery 多 Worker

### 9.3 监控告警
- Prometheus + Grafana 监控
- 日志聚合（ELK）
- 告警通知（邮件/钉钉）

## 10. 开发计划

### 10.1 第一阶段（MVP）
- 用户认证与权限
- 数据源管理
- SQL 查询
- Excel 导出

### 10.2 第二阶段
- NL2SQL 查询
- PDF 生成
- 图表渲染
- 模板管理

### 10.3 第三阶段
- 异步导出
- 模板分享
- 版本控制
- 性能优化

## 11. 风险与挑战

### 11.1 技术风险
- NL2SQL 准确性依赖 LLM 质量
- 大数据量查询性能问题
- 多数据源兼容性问题

### 11.2 业务风险
- 用户权限管理复杂度高
- 模板版本控制冲突
- 数据安全合规要求

### 11.3 缓解措施
- NL2SQL 采用规则引擎 + LLM 混合方案
- 大查询强制异步处理
- 数据源抽象层统一接口
- 严格的权限测试
- 完善的审计日志
