# RCA 根因分析功能实现计划

**目标**: 在 myreport 中集成零售异常根因分析，支持异常检测 → 维度下钻 → 归因推理完整链路。

**架构**: 后端新增 RCA 模块（API + Service + Celery 异步任务），核心检测和下钻 SQL 全部走现有 Doris 数据源（通过 `db_executor.py`），PostgreSQL 只存配置和分析结果。前端新增 RCA 仪表盘页面。

**技术栈**: FastAPI, SQLAlchemy, Celery, Vue 3 + Element Plus

**Doris 数据源映射**:

| 分析场景 | Doris 表 | 关键字段 |
|----------|----------|----------|
| 异常检测（预警标识） | `ads_cockpit_fd_store_ware_d` | extra_stock, lack_stock, stasis_sales, negative_profit 等 |
| 异常检测（已有异常表） | `ads_cockpit_qck_store_ware_abnormal_d_v1` | 异常商品明细 |
| 金额/销量波动 | `store_ware_*_agg_d_v1` | actual_sale_untaxed_amt, sale_num |
| 同期对比 | `ware_pcat_overview` | current_stage / same_stage |
| 维度下钻 | 同上 + `dim_store` | 门店/类目/商品/供应商 |
| 归因-促销 | `schedule_*` | 档期信息 |
| 归因-供应链 | `supply_ware_d` | scm_book_num, scm_receive_num |
| 归因-预算 | `store_cat_budget_d_v1` | budget_amt |

---

## 任务分解

### 任务 1：配置 + 模型 + Schema

**目标**: 新增 RCA 配置项、PostgreSQL 数据模型、Pydantic Schema

**文件**:
- 修改: `backend/app/config.py`
- 创建: `backend/app/models/rca.py`
- 创建: `backend/app/schemas/rca.py`
- 修改: `backend/app/models/__init__.py`

**步骤 1: config.py 新增 RCA 配置项**

在 `Settings` 类中添加:

```python
# RCA 根因分析
rca_enabled: bool = True
rca_default_data_source_id: int = 0        # 默认 Doris 数据源 ID（0=从配置读取）
rca_default_group_id: int = 123             # 默认集团 ID
rca_max_drill_levels: int = 4               # 最大下钻层数
rca_anomaly_threshold: float = 10.0         # 默认异常阈值（百分比）
rca_task_soft_time_limit: int = 300         # 分析任务软超时（秒）
rca_task_time_limit: int = 600              # 分析任务硬超时（秒）
rca_task_max_retries: int = 1
```

**步骤 2: 创建 `backend/app/models/rca.py`**

```python
"""RCA 根因分析数据模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class RcaMetricConfig(Base):
"""RCA 指标监控配置"""
__tablename__ = "rca_metric_configs"

id = Column(Integer, primary_key=True, autoincrement=True)
name = Column(String(100), nullable=False, comment="指标名称，如 total_sales")
label = Column(String(200), nullable=False, comment="展示名，如 实销金额")
metric_field = Column(String(200), nullable=False, comment="Doris 表字段名，如 actual_sale_untaxed_amt")
source_table = Column(String(300), nullable=False, comment="Doris 表全名")
threshold_type = Column(String(50), nullable=False, default="percent_change",
comment="阈值类型: percent_change / absolute / zscore")
threshold_value = Column(Float, nullable=False, default=10.0, comment="阈值")
compare_type = Column(String(20), nullable=False, default="mom",
comment="对比类型: yoy(同比) / mom(环比) / wow(周环比)")
drill_dimensions = Column(JSON, nullable=False,
comment='下钻维度列表，如 ["operation_category1_name","store_code","matnr"]')
group_id = Column(Integer, nullable=False, comment="集团 ID")
data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, comment="数据源 ID")
enabled = Column(Boolean, default=True, comment="是否启用")
created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RcaAnalysisTask(Base):
"""RCA 分析任务"""
__tablename__ = "rca_analysis_tasks"

id = Column(Integer, primary_key=True, autoincrement=True)
task_id = Column(String(64), nullable=False, index=True, comment="任务唯一 ID (UUID)")
metric_config_id = Column(Integer, ForeignKey("rca_metric_configs.id"), nullable=False)
analysis_date = Column(Date, nullable=False, comment="分析的目标日期")
period_days = Column(Integer, nullable=False, default=7, comment="对比周期天数")
status = Column(String(20), nullable=False, default="pending",
comment="pending / running / completed / failed")
anomaly_count = Column(Integer, nullable=True, comment="发现的异常数量")
summary = Column(JSON, nullable=True, comment="分析结论摘要")
error_message = Column(Text, nullable=True)
created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
created_at = Column(DateTime(timezone=True), server_default=func.now())
completed_at = Column(DateTime(timezone=True), nullable=True)


class RcaAnomaly(Base):
"""RCA 异常发现"""
__tablename__ = "rca_anomalies"

id = Column(Integer, primary_key=True, autoincrement=True)
task_id = Column(String(64), nullable=False, index=True, comment="关联 RcaAnalysisTask.task_id")
metric_name = Column(String(100), nullable=False)
dimension_path = Column(JSON, nullable=False,
comment='维度路径，如 {"operation_category1_name":"电子产品","store_code":"S001"}')
current_value = Column(Float, nullable=True, comment="当前值")
baseline_value = Column(Float, nullable=True, comment="基线值")
change_pct = Column(Float, nullable=True, comment="变化百分比")
severity = Column(String(20), nullable=False, default="warning",
comment="critical / warning / info")
contribution_pct = Column(Float, nullable=True, comment="对总体异常的贡献度(%)")
root_cause_hint = Column(Text, nullable=True, comment="归因推理结论")
drill_details = Column(JSON, nullable=True, comment="下钻详情 JSON")
created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**步骤 3: 创建 `backend/app/schemas/rca.py`**

```python
"""RCA 请求/响应 Schema"""
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RcaMetricConfigCreate(BaseModel):
name: str
label: str
metric_field: str
source_table: str
threshold_type: str = "percent_change"
threshold_value: float = 10.0
compare_type: str = "mom"
drill_dimensions: List[str] = ["operation_category1_name", "store_code", "matnr"]
group_id: int
data_source_id: int


class RcaMetricConfigResponse(BaseModel):
id: int
name: str
label: str
metric_field: str
source_table: str
threshold_type: str
threshold_value: float
compare_type: str
drill_dimensions: List[str]
group_id: int
data_source_id: int
enabled: bool
created_at: Optional[datetime] = None

class Config:
from_attributes = True


class RcaAnalyzeRequest(BaseModel):
metric_config_id: int
analysis_date: date = Field(default_factory=date.today)
period_days: int = 7


class RcaDrillDownRequest(BaseModel):
task_id: str
metric_name: str
dimension: Optional[str] = None
dimension_value: Optional[str] = None
filters: Optional[Dict[str, Any]] = None


class RcaAnomalyResponse(BaseModel):
id: int
task_id: str
metric_name: str
dimension_path: Dict[str, Any]
current_value: Optional[float] = None
baseline_value: Optional[float] = None
change_pct: Optional[float] = None
severity: str
contribution_pct: Optional[float] = None
root_cause_hint: Optional[str] = None
drill_details: Optional[Dict[str, Any]] = None
created_at: Optional[datetime] = None

class Config:
from_attributes = True


class RcaTaskResponse(BaseModel):
id: int
task_id: str
metric_config_id: int
analysis_date: date
period_days: int
status: str
anomaly_count: Optional[int] = None
summary: Optional[Dict[str, Any]] = None
error_message: Optional[str] = None
created_at: Optional[datetime] = None
completed_at: Optional[datetime] = None

class Config:
from_attributes = True


class RcaDrillResult(BaseModel):
dimension: str
dimension_value: str
current_value: float
baseline_value: float
change_pct: float
contribution_pct: float
```

**步骤 4: 更新 `backend/app/models/__init__.py`**

添加 import:
```python
from app.models.rca import RcaMetricConfig, RcaAnalysisTask, RcaAnomaly
```

和 `__all__` 列表中追加 `"RcaMetricConfig"`, `"RcaAnalysisTask"`, `"RcaAnomaly"`。

**步骤 5: 执行 Alembic 迁移**

```bash
cd /home/zhou/myreport/backend
alembic revision --autogenerate -m "add rca tables"
alembic upgrade head
```

---

### 任务 2：RCA Service 核心引擎

**目标**: 实现异常检测 + 维度下钻 + 归因推理的核心 SQL 生成逻辑

**文件**:
- 创建: `backend/app/services/rca_service.py`
- 创建: `backend/app/utils/rca_sql_builder.py`

**步骤 1: 创建 `backend/app/utils/rca_sql_builder.py`**

SQL 构建器，负责生成 Doris 查询 SQL。核心类 `RcaSqlBuilder`：
- `build_comparison_sql()` — 对比当前期与基线期，输出变化百分比
- `build_drill_down_sql()` — 按指定维度 GROUP BY，输出贡献度排名
- `_base_filter()` — 统一的 group_id + exclude_flag + 日期范围条件

关键 CTE 模式：
```sql
WITH current_period AS (
SELECT dim, SUM(metric) AS current_val FROM table WHERE 日期=当前期 GROUP BY dim
),
baseline_period AS (
SELECT dim, SUM(metric) AS baseline_val FROM table WHERE 日期=基线期 GROUP BY dim
),
diff AS (
SELECT dim, current_val, baseline_val, current_val - baseline_val AS abs_diff
FROM current_period FULL OUTER JOIN baseline_period ...
)
SELECT *, abs_diff/SUM(abs_diff) OVER() AS contribution_pct
FROM diff WHERE abs_diff < 0 ORDER BY abs_diff ASC
```

**步骤 2: 创建 `backend/app/services/rca_service.py`**

核心服务类 `RcaService`，方法：
- `list_configs()` / `create_config()` / `delete_config()` — 指标配置 CRUD
- `trigger_analysis()` — 创建分析任务（返回 task，异步执行由 Celery 负责）
- `execute_analysis(task_id)` — 执行分析：调用 SqlBuilder 生成 SQL → 通过 db_executor 执行 → 识别异常 → 写入 rca_anomalies 表
- `get_anomalies(task_id)` — 查询异常列表
- `drill_down(request)` — 手动下钻查询
- `list_tasks()` — 分析任务列表

execute_analysis 流程：
1. 读取 metric_config 获取 source_table, metric_field, group_id, drill_dimensions, threshold
2. 计算当前期/基线期的 dt 范围
3. 用 build_comparison_sql 获取总体变化
4. 逐层调用 build_drill_down_sql，对每个维度取 Top5 异常
5. 变化超过阈值的写入 rca_anomalies 表
6. 更新 task 状态为 completed

---

### 任务 3：RCA API 路由

**目标**: 暴露 REST API 端点

**文件**:
- 创建: `backend/app/api/rca.py`
- 修改: `backend/app/main.py` (注册路由)

**路由设计**:
```
POST   /api/rca/configs              创建指标配置
GET    /api/rca/configs              获取配置列表
DELETE /api/rca/configs/{id}         删除配置

POST   /api/rca/analyze              触发分析任务（同步执行，返回结果）
GET    /api/rca/tasks                分析任务列表
GET    /api/rca/tasks/{task_id}      任务详情
GET    /api/rca/tasks/{task_id}/anomalies  异常列表

POST   /api/rca/drill-down           手动下钻查询
```

**步骤 1: 创建 `backend/app/api/rca.py`**

```python
"""RCA 根因分析 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.rca import (
RcaMetricConfigCreate, RcaMetricConfigResponse,
RcaAnalyzeRequest, RcaAnomalyResponse, RcaTaskResponse,
RcaDrillDownRequest,
)
from app.services.rca_service import RcaService

router = APIRouter(prefix="/api/rca", tags=["RCA根因分析"])

@router.get("/configs", response_model=List[RcaMetricConfigResponse])
async def list_configs(db: Session = Depends(get_db), uid: int = Depends(get_current_user_id)):
return RcaService(db).list_configs()

@router.post("/configs", response_model=RcaMetricConfigResponse)
async def create_config(
payload: RcaMetricConfigCreate,
db: Session = Depends(get_db),
uid: int = Depends(get_current_user_id),
):
return RcaService(db).create_config(payload.model_dump(), uid)

@router.delete("/configs/{config_id}")
async def delete_config(config_id: int, db: Session = Depends(get_db), uid: int = Depends(get_current_user_id)):
ok = RcaService(db).delete_config(config_id)
if not ok: raise HTTPException(404, "配置不存在")
return {"ok": True}

@router.post("/analyze", response_model=RcaTaskResponse)
async def trigger_analyze(
payload: RcaAnalyzeRequest,
db: Session = Depends(get_db),
uid: int = Depends(get_current_user_id),
):
"""触发分析（同步执行，大指标建议用 Celery 异步）"""
svc = RcaService(db)
task = svc.trigger_analysis(payload.model_dump(), uid)
try:
svc.execute_analysis(task.task_id)
task = db.query(type(task)).filter(type(task).task_id == task.task_id).first()
except Exception as e:
task = db.query(type(task)).filter(type(task).task_id == task.task_id).first()
return task

@router.get("/tasks", response_model=List[RcaTaskResponse])
async def list_tasks(
limit: int = 20,
db: Session = Depends(get_db),
uid: int = Depends(get_current_user_id),
):
return RcaService(db).list_tasks(limit)

@router.get("/tasks/{task_id}", response_model=RcaTaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db), uid: int = Depends(get_current_user_id)):
from app.models.rca import RcaAnalysisTask
task = db.query(RcaAnalysisTask).filter(RcaAnalysisTask.task_id == task_id).first()
if not task: raise HTTPException(404, "任务不存在")
return task

@router.get("/tasks/{task_id}/anomalies", response_model=List[RcaAnomalyResponse])
async def get_anomalies(task_id: str, db: Session = Depends(get_db), uid: int = Depends(get_current_user_id)):
return RcaService(db).get_anomalies(task_id)

@router.post("/drill-down")
async def drill_down(
payload: RcaDrillDownRequest,
db: Session = Depends(get_db),
uid: int = Depends(get_current_user_id),
):
rows = RcaService(db).drill_down(payload.model_dump())
return {"rows": rows}
```

**步骤 2: 修改 `backend/app/main.py`**

在 import 区域添加:
```python
from app.api import rca as rca_api
```

在路由注册区域添加:
```python
app.include_router(rca_api.router)
```

**步骤 3: 修改 `backend/app/config.py`**

在 Settings 类末尾添加 RCA 配置项（如任务 1 所述）。

---

### 任务 4：Celery 异步任务

**目标**: 大批量分析通过 Celery 异步执行

**文件**:
- 创建: `backend/app/tasks/rca_tasks.py`

**步骤 1: 创建 `backend/app/tasks/rca_tasks.py`**

```python
"""RCA 异步分析任务"""
from celery import shared_task
from app.core.database import SessionLocal
from app.services.rca_service import RcaService
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

@shared_task(
bind=True,
max_retries=settings.rca_task_max_retries,
soft_time_limit=settings.rca_task_soft_time_limit,
time_limit=settings.rca_task_time_limit,
)
def run_rca_analysis(self, task_id: str):
"""异步执行 RCA 分析"""
db = SessionLocal()
try:
svc = RcaService(db)
result = svc.execute_analysis(task_id)
logger.info(f"RCA analysis completed: {result}")
return result
except Exception as e:
logger.error(f"RCA analysis failed: {e}", exc_info=True)
raise
finally:
db.close()
```

**步骤 2: 修改 `backend/app/api/rca.py`**

在 `trigger_analyze` 端点中，可选改为异步：
```python
# 同步模式（当前实现）
svc.execute_analysis(task.task_id)

# 异步模式（大批量时启用）
from app.tasks.rca_tasks import run_rca_analysis
run_rca_analysis.delay(task.task_id)
```

---

### 任务 5：前端页面

**目标**: RCA 仪表盘 + 配置管理 + 下钻详情页

**文件**:
- 创建: `frontend/src/api/rca.js`
- 创建: `frontend/src/views/RcaDashboard.vue`
- 创建: `frontend/src/views/RcaAnomalies.vue`
- 修改: `frontend/src/router/index.js`
- 修改: `frontend/src/components/Sidebar.vue`

**步骤 1: 创建 `frontend/src/api/rca.js`**

```javascript
import request from '@/api/request'

export function getRcaConfigs() {
return request.get('/api/rca/configs')
}

export function createRcaConfig(data) {
return request.post('/api/rca/configs', data)
}

export function deleteRcaConfig(id) {
return request.delete(`/api/rca/configs/${id}`)
}

export function triggerRcaAnalyze(data) {
return request.post('/api/rca/analyze', data)
