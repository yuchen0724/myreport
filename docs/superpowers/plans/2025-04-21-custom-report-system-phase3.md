# 自定义报表查询系统 - 第三阶段实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现异步导出、模板分享、版本控制和性能优化功能，提升系统的可扩展性和用户体验。

**架构：** 基于 Celery + Redis 的异步任务处理架构，结合现有的 FastAPI 单体应用，实现高性能的异步导出和完善的模板管理功能。

**技术栈：** Celery、Redis、FastAPI、PostgreSQL、Vue 3、Element Plus

---

## 文件结构

### 后端文件
- `backend/app/celery_app.py` - Celery 应用配置
- `backend/app/tasks/export_tasks.py` - 异步导出任务
- `backend/app/api/async_export.py` - 异步导出 API
- `backend/app/services/async_export_service.py` - 异步导出服务
- `backend/app/services/cache_service.py` - 缓存服务
- `backend/app/middleware/rate_limit.py` - 限流中间件
- `backend/app/utils/query_optimizer.py` - 查询优化器
- `backend/app/models/export_task.py` - 导出任务模型（已存在，需扩展）
- `backend/app/schemas/async_export.py` - 异步导出模式
- `backend/tests/test_async_export.py` - 异步导出测试
- `backend/tests/test_cache.py` - 缓存测试
- `backend/tests/test_rate_limit.py` - 限流测试

### 前端文件
- `frontend/src/api/async_export.js` - 异步导出 API
- `frontend/src/views/AsyncExport.vue` - 异步导出页面
- `frontend/src/components/ExportProgress.vue` - 导出进度组件
- `frontend/src/views/TemplateShare.vue` - 模板分享页面
- `frontend/src/views/TemplateVersionHistory.vue` - 模板版本历史页面
- `frontend/src/components/VersionDiff.vue` - 版本对比组件

### 配置文件
- `backend/celery_config.py` - Celery 配置
- `backend/requirements.txt` - 添加 Celery 相关依赖

---

## 模块 1：异步导出功能

### 任务 1：配置 Celery 应用

**文件：**
- 创建：`backend/celery_config.py`
- 创建：`backend/app/celery_app.py`
- 修改：`backend/requirements.txt`

- [ ] **步骤 1：编写 Celery 配置文件**

```python
# backend/celery_config.py
from celery import Celery
import os

# Redis 配置
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# 创建 Celery 应用
celery_app = Celery(
    'myreport',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.export_tasks']
)

# 配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟超时
    task_soft_time_limit=25 * 60,  # 25分钟软超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 任务路由
celery_app.conf.task_routes = {
    'app.tasks.export_tasks.*': {'queue': 'export'},
}

# 自动发现任务
celery_app.autodiscover_tasks(['app.tasks'])
```

- [ ] **步骤 2：编写 Celery 应用初始化文件**

```python
# backend/app/celery_app.py
from celery import Celery
import os

def create_celery_app():
    """创建 Celery 应用实例"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    celery = Celery(
        'myreport',
        broker=redis_url,
        backend=redis_url,
    )
    
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Shanghai',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,
        task_soft_time_limit=25 * 60,
    )
    
    return celery

celery_app = create_celery_app()
```

- [ ] **步骤 3：更新依赖文件**

```bash
# 添加到 backend/requirements.txt
celery==5.3.4
redis==5.0.1
```

- [ ] **步骤 4：安装依赖**

```bash
cd /home/zhou/myreport/backend
pip install celery==5.3.4 redis==5.0.1 --break-system-packages
```

- [ ] **步骤 5：验证 Celery 配置**

```bash
cd /home/zhou/myreport/backend
python3 -c "from celery_config import celery_app; print('✅ Celery 配置成功')"
```

- [ ] **步骤 6：Commit**

```bash
cd /home/zhou/myreport
git add backend/celery_config.py backend/app/celery_app.py backend/requirements.txt
git commit -m "feat: 添加 Celery 配置"
```

---

### 任务 2：实现异步导出任务

**文件：**
- 创建：`backend/app/tasks/export_tasks.py`
- 修改：`backend/app/models/export_task.py`

- [ ] **步骤 1：编写异步导出任务**

```python
# backend/app/tasks/export_tasks.py
from celery import shared_task
from app.core.database import SessionLocal
from app.models.export_task import ExportTask
from app.services.report_service import ReportService
from app.services.query_service import QueryService
from datetime import datetime
import traceback

@shared_task(bind=True)
def export_excel_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 Excel 任务"""
    db = SessionLocal()
    try:
        # 更新任务状态为运行中
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.status = "RUNNING"
        task.started_at = datetime.now()
        db.commit()
        
        # 执行查询
        query_service = QueryService(db)
        result = query_service.execute_query(data_source_id, sql, {})
        
        # 生成 Excel
        report_service = ReportService(db)
        from app.schemas.report import ExcelExportRequest
        export_request = ExcelExportRequest(
            data_source_id=data_source_id,
            sql=sql,
            filename=f"export_{task_id}.xlsx"
        )
        
        excel_data = report_service.generate_excel(export_request, user_id)
        
        # 保存文件
        file_path = f"/tmp/exports/{task_id}.xlsx"
        with open(file_path, 'wb') as f:
            f.write(excel_data.getvalue())
        
        # 更新任务状态为成功
        task.status = "SUCCESS"
        task.file_path = file_path
        task.completed_at = datetime.now()
        task.row_count = result.total
        db.commit()
        
        return {"status": "success", "file_path": file_path}
        
    except Exception as e:
        # 更新任务状态为失败
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
        
        # 记录错误
        error_trace = traceback.format_exc()
        print(f"导出任务失败: {task_id}\n{error_trace}")
        
        # 重试
        raise self.retry(exc=e, countdown=60, max_retries=3)
        
    finally:
        db.close()

@shared_task(bind=True)
def export_pdf_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 PDF 任务"""
    db = SessionLocal()
    try:
        # 更新任务状态为运行中
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.status = "RUNNING"
        task.started_at = datetime.now()
        db.commit()
        
        # 执行查询
        query_service = QueryService(db)
        result = query_service.execute_query(data_source_id, sql, {})
        
        # 生成 PDF
        report_service = ReportService(db)
        from app.schemas.report import PDFExportRequest
        export_request = PDFExportRequest(
            data_source_id=data_source_id,
            sql=sql,
            filename=f"export_{task_id}.pdf"
        )
        
        pdf_data = report_service.generate_pdf(export_request, user_id)
        
        # 保存文件
        file_path = f"/tmp/exports/{task_id}.pdf"
        with open(file_path, 'wb') as f:
            f.write(pdf_data.getvalue())
        
        # 更新任务状态为成功
        task.status = "SUCCESS"
        task.file_path = file_path
        task.completed_at = datetime.now()
        task.row_count = result.total
        db.commit()
        
        return {"status": "success", "file_path": file_path}
        
    except Exception as e:
        # 更新任务状态为失败
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
        
        # 记录错误
        error_trace = traceback.format_exc()
        print(f"PDF 导出任务失败: {task_id}\n{error_trace}")
        
        # 重试
        raise self.retry(exc=e, countdown=60, max_retries=3)
        
    finally:
        db.close()
```

- [ ] **步骤 2：扩展导出任务模型**

```python
# backend/app/models/export_task.py
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class ExportTask(Base):
    __tablename__ = "export_tasks"
    
    id = Column(String(50), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED
    file_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    row_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    user = relationship("User", back_populates="export_tasks")
    template = relationship("Template", back_populates="export_tasks")
```

- [ ] **步骤 3：创建导出目录**

```bash
mkdir -p /tmp/exports
chmod 755 /tmp/exports
```

- [ ] **步骤 4：验证任务导入**

```bash
cd /home/zhou/myreport/backend
python3 -c "from app.tasks.export_tasks import export_excel_async; print('✅ 导出任务导入成功')"
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/tasks/export_tasks.py backend/app/models/export_task.py
git commit -m "feat: 实现异步导出任务"
```

---

### 任务 3：创建异步导出 API

**文件：**
- 创建：`backend/app/api/async_export.py`
- 创建：`backend/app/schemas/async_export.py`
- 创建：`backend/app/services/async_export_service.py`
- 修改：`backend/app/main.py`

- [ ] **步骤 1：编写异步导出模式**

```python
# backend/app/schemas/async_export.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AsyncExportRequest(BaseModel):
    """异步导出请求"""
    data_source_id: int = Field(..., description="数据源ID")
    sql: str = Field(..., description="SQL查询语句")
    export_type: str = Field(..., description="导出类型: excel/pdf")
    filename: Optional[str] = Field(None, description="文件名")

class AsyncExportResponse(BaseModel):
    """异步导出响应"""
    task_id: str
    status: str
    message: str

class ExportTaskStatus(BaseModel):
    """导出任务状态"""
    id: str
    status: str
    file_path: Optional[str]
    error_message: Optional[str]
    row_count: Optional[int]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: float  # 0-100
```

- [ ] **步骤 2：编写异步导出服务**

```python
# backend/app/services/async_export_service.py
from typing import Optional
from sqlalchemy.orm import Session
from app.models.export_task import ExportTask
from app.schemas.async_export import AsyncExportRequest, AsyncExportResponse
from app.tasks.export_tasks import export_excel_async, export_pdf_async
import uuid

class AsyncExportService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_export_task(self, request: AsyncExportRequest, user_id: int) -> AsyncExportResponse:
        """创建异步导出任务"""
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = ExportTask(
            id=task_id,
            user_id=user_id,
            status="PENDING",
        )
        self.db.add(task)
        self.db.commit()
        
        # 根据导出类型调度任务
        if request.export_type.lower() == "excel":
            export_excel_async.delay(task_id, request.data_source_id, request.sql, user_id)
        elif request.export_type.lower() == "pdf":
            export_pdf_async.delay(task_id, request.data_source_id, request.sql, user_id)
        else:
            raise ValueError(f"不支持的导出类型: {request.export_type}")
        
        return AsyncExportResponse(
            task_id=task_id,
            status="PENDING",
            message="导出任务已创建，正在处理中"
        )
    
    def get_task_status(self, task_id: str) -> Optional[ExportTask]:
        """获取任务状态"""
        return self.db.query(ExportTask).filter(ExportTask.id == task_id).first()
    
    def get_user_tasks(self, user_id: int, skip: int = 0, limit: int = 100):
        """获取用户的导出任务列表"""
        return self.db.query(ExportTask).filter(
            ExportTask.user_id == user_id
        ).order_by(ExportTask.created_at.desc()).offset(skip).limit(limit).all()
```

- [ ] **步骤 3：编写异步导出 API**

```python
# backend/app/api/async_export.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.async_export import AsyncExportRequest, AsyncExportResponse, ExportTaskStatus
from app.services.async_export_service import AsyncExportService

router = APIRouter(prefix="/api/async-export", tags=["异步导出"])

@router.post("/create", response_model=AsyncExportResponse, status_code=status.HTTP_201_CREATED)
async def create_export_task(
    request: AsyncExportRequest,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """创建异步导出任务"""
    service = AsyncExportService(db)
    try:
        return service.create_export_task(request, current_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/task/{task_id}", response_model=ExportTaskStatus)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取导出任务状态"""
    service = AsyncExportService(db)
    task = service.get_task_status(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 计算进度
    progress = 0.0
    if task.status == "RUNNING":
        progress = 50.0
    elif task.status == "SUCCESS":
        progress = 100.0
    
    return ExportTaskStatus(
        id=task.id,
        status=task.status,
        file_path=task.file_path,
        error_message=task.error_message,
        row_count=task.row_count,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        progress=progress
    )

@router.get("/tasks", response_model=List[ExportTaskStatus])
async def get_user_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """获取用户的导出任务列表"""
    service = AsyncExportService(db)
    tasks = service.get_user_tasks(current_user_id, skip, limit)
    
    return [
        ExportTaskStatus(
            id=task.id,
            status=task.status,
            file_path=task.file_path,
            error_message=task.error_message,
            row_count=task.row_count,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            progress=100.0 if task.status == "SUCCESS" else (50.0 if task.status == "RUNNING" else 0.0)
        )
        for task in tasks
    ]

@router.get("/download/{task_id}")
async def download_export_file(
    task_id: str,
    db: Session = Depends(get_db)
):
    """下载导出文件"""
    service = AsyncExportService(db)
    task = service.get_task_status(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if task.status != "SUCCESS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务尚未完成"
        )
    
    if not task.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    from fastapi.responses import FileResponse
    import os
    
    if not os.path.exists(task.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已被删除"
        )
    
    return FileResponse(
        task.file_path,
        media_type='application/octet-stream',
        filename=os.path.basename(task.file_path)
    )
```

- [ ] **步骤 4：注册路由**

```python
# backend/app/main.py
from app.api import auth, data_sources, query, report, nl2sql, charts, templates, stats, async_export

# 注册路由
app.include_router(async_export.router)
```

- [ ] **步骤 5：验证 API 导入**

```bash
cd /home/zhou/myreport/backend
python3 -c "from app.api.async_export import router; print('✅ 异步导出 API 导入成功')"
```

- [ ] **步骤 6：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/api/async_export.py backend/app/schemas/async_export.py backend/app/services/async_export_service.py backend/app/main.py
git commit -m "feat: 添加异步导出 API"
```

---

### 任务 4：创建异步导出前端页面

**文件：**
- 创建：`frontend/src/api/async_export.js`
- 创建：`frontend/src/views/AsyncExport.vue`
- 创建：`frontend/src/components/ExportProgress.vue`
- 修改：`frontend/src/router/index.js`

- [ ] **步骤 1：编写前端 API 调用**

```javascript
// frontend/src/api/async_export.js
import request from "@/utils/request"

export function createExportTask(data) {
  return request({
    url: "/async-export/create",
    method: "post",
    data
  })
}

export function getTaskStatus(taskId) {
  return request({
    url: `/async-export/task/${taskId}`,
    method: "get"
  })
}

export function getUserTasks(params) {
  return request({
    url: "/async-export/tasks",
    method: "get",
    params
  })
}

export function downloadExportFile(taskId) {
  return request({
    url: `/async-export/download/${taskId}`,
    method: "get",
    responseType: "blob"
  })
}
```

- [ ] **步骤 2：编写导出进度组件**

```vue
<!-- frontend/src/components/ExportProgress.vue -->
<template>
  <div class="export-progress">
    <el-progress
      :percentage="progress"
      :status="status"
      :stroke-width="20"
    >
      <template #default="{ percentage }">
        <span class="percentage-value">{{ percentage }}%</span>
      </template>
    </el-progress>
    <div class="status-text">
      <el-tag :type="statusType">{{ statusText }}</el-tag>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'PENDING'
  },
  progress: {
    type: Number,
    default: 0
  }
})

const statusType = computed(() => {
  const statusMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'SUCCESS': 'success',
    'FAILED': 'danger'
  }
  return statusMap[props.status] || 'info'
})

const statusText = computed(() => {
  const textMap = {
    'PENDING': '等待中',
    'RUNNING': '处理中',
    'SUCCESS': '已完成',
    'FAILED': '失败'
  }
  return textMap[props.status] || '未知'
})
</script>

<style scoped>
.export-progress {
  padding: 20px;
}

.percentage-value {
  font-weight: bold;
  color: #409eff;
}

.status-text {
  margin-top: 10px;
  text-align: center;
}
</style>
```

- [ ] **步骤 3：编写异步导出页面**

```vue
<!-- frontend/src/views/AsyncExport.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="async-export">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>异步导出</span>
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

          <el-form-item label="SQL查询">
            <el-input
              v-model="form.sql"
              type="textarea"
              :rows="5"
              placeholder="请输入SQL查询语句"
            />
          </el-form-item>

          <el-form-item label="导出类型">
            <el-radio-group v-model="form.export_type">
              <el-radio label="excel">Excel</el-radio>
              <el-radio label="pdf">PDF</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleCreateExport" :loading="creating">
              创建导出任务
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>导出任务列表</span>
            <el-button @click="loadTasks">刷新</el-button>
          </div>
        </template>

        <el-table :data="tasks" style="width: 100%">
          <el-table-column prop="id" label="任务ID" width="200" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="progress" label="进度" width="150">
            <template #default="{ row }">
              <el-progress :percentage="row.progress" :stroke-width="10" />
            </template>
          </el-table-column>
          <el-table-column prop="row_count" label="行数" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'SUCCESS'"
                type="primary"
                size="small"
                @click="handleDownload(row.id)"
              >
                下载
              </el-button>
              <el-button
                v-if="row.status === 'FAILED'"
                type="danger"
                size="small"
                @click="handleViewError(row)"
              >
                查看错误
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </Layout>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { createExportTask, getTaskStatus, getUserTasks, downloadExportFile } from '@/api/async_export'
import { getDataSourceList } from '@/api/data_source'

const form = ref({
  data_source_id: null,
  sql: '',
  export_type: 'excel'
})

const dataSources = ref([])
const tasks = ref([])
const creating = ref(false)
let refreshInterval = null

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSources.value = response
  } catch (error) {
    ElMessage.error('加载数据源失败')
  }
}

const loadTasks = async () => {
  try {
    const response = await getUserTasks()
    tasks.value = response
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  }
}

const handleCreateExport = async () => {
  if (!form.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.sql) {
    ElMessage.warning('请输入SQL查询')
    return
  }

  creating.value = true
  try {
    const response = await createExportTask(form.value)
    ElMessage.success('导出任务已创建')
    loadTasks()
  } catch (error) {
    ElMessage.error('创建导出任务失败')
  } finally {
    creating.value = false
  }
}

const handleDownload = async (taskId) => {
  try {
    const response = await downloadExportFile(taskId)
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `export_${taskId}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载文件失败')
  }
}

const handleViewError = (task) => {
  ElMessage.error(task.error_message || '导出失败')
}

const getStatusType = (status) => {
  const typeMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'SUCCESS': 'success',
    'FAILED': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'PENDING': '等待中',
    'RUNNING': '处理中',
    'SUCCESS': '已完成',
    'FAILED': '失败'
  }
  return textMap[status] || '未知'
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadDataSources()
  loadTasks()
  // 每5秒刷新一次任务状态
  refreshInterval = setInterval(loadTasks, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.async-export {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
```

- [ ] **步骤 4：添加路由**

```javascript
// frontend/src/router/index.js
{
  path: "/async-export",
  name: "AsyncExport",
  component: () => import("@/views/AsyncExport.vue"),
  meta: { requiresAuth: true }
}
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add frontend/src/api/async_export.js frontend/src/views/AsyncExport.vue frontend/src/components/ExportProgress.vue frontend/src/router/index.js
git commit -m "feat: 添加异步导出前端页面"
```

---

## 模块 2：模板分享功能

### 任务 5：实现模板分享功能

**文件：**
- 修改：`backend/app/services/template_service.py`
- 修改：`backend/app/api/templates.py`
- 创建：`frontend/src/views/TemplateShare.vue`
- 修改：`frontend/src/router/index.js`

- [ ] **步骤 1：扩展模板服务**

```python
# backend/app/services/template_service.py
# 在 TemplateService 类中添加以下方法

def share_template(self, template_id: int, user_ids: List[int], shared_by: int) -> bool:
    """分享模板给指定用户"""
    from app.models.template_share import TemplateShare
    
    # 验证模板所有权
    template = self.get_template(template_id)
    if not template or template.created_by != shared_by:
        raise ValueError("无权限分享此模板")
    
    # 删除旧的分享记录
    self.db.query(TemplateShare).filter(
        TemplateShare.template_id == template_id
    ).delete()
    
    # 创建新的分享记录
    for user_id in user_ids:
        share = TemplateShare(
            template_id=template_id,
            user_id=user_id,
            shared_by=shared_by
        )
        self.db.add(share)
    
    self.db.commit()
    return True

def get_shared_templates(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Template]:
    """获取分享给用户的模板列表"""
    from app.models.template_share import TemplateShare
    
    shared_template_ids = self.db.query(TemplateShare.template_id).filter(
        TemplateShare.user_id == user_id
    ).all()
    
    template_ids = [t[0] for t in shared_template_ids]
    
    if not template_ids:
        return []
    
    return self.db.query(Template).filter(
        Template.id.in_(template_ids)
    ).order_by(Template.created_at.desc()).offset(skip).limit(limit).all()

def get_template_shares(self, template_id: int) -> List[int]:
    """获取模板的分享用户列表"""
    from app.models.template_share import TemplateShare
    
    shares = self.db.query(TemplateShare.user_id).filter(
        TemplateShare.template_id == template_id
    ).all()
    
    return [s[0] for s in shares]
```

- [ ] **步骤 2：扩展模板 API**

```python
# backend/app/api/templates.py
# 添加以下路由

@router.post("/{template_id}/share")
async def share_template(
    template_id: int,
    user_ids: List[int],
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """分享模板"""
    service = TemplateService(db)
    try:
        service.share_template(template_id, user_ids, current_user_id)
        return {"message": "分享成功"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/shared")
async def get_shared_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """获取分享给我的模板列表"""
    service = TemplateService(db)
    templates = service.get_shared_templates(current_user_id, skip, limit)
    return templates

@router.get("/{template_id}/shares")
async def get_template_shares(
    template_id: int,
    db: Session = Depends(get_db)
):
    """获取模板的分享用户列表"""
    service = TemplateService(db)
    user_ids = service.get_template_shares(template_id)
    return {"user_ids": user_ids}
```

- [ ] **步骤 3：编写模板分享前端页面**

```vue
<!-- frontend/src/views/TemplateShare.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="template-share">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>模板分享</span>
          </div>
        </template>

        <el-form :model="form" label-width="120px">
          <el-form-item label="选择模板">
            <el-select v-model="form.template_id" placeholder="请选择模板">
              <el-option
                v-for="template in myTemplates"
                :key="template.id"
                :label="template.name"
                :value="template.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="分享给用户">
            <el-select
              v-model="form.user_ids"
              multiple
              placeholder="请选择用户"
            >
              <el-option
                v-for="user in users"
                :key="user.id"
                :label="user.username"
                :value="user.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleShare" :loading="sharing">
              分享
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>分享给我的模板</span>
          </div>
        </template>

        <el-table :data="sharedTemplates" style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="模板名称" />
          <el-table-column prop="description" label="描述" />
          <el-table-column prop="created_by" label="创建者" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="handleUse(row)">
                使用
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getTemplateList, shareTemplate, getSharedTemplates } from '@/api/template'

const form = ref({
  template_id: null,
  user_ids: []
})

const myTemplates = ref([])
const sharedTemplates = ref([])
const users = ref([])
const sharing = ref(false)

const loadMyTemplates = async () => {
  try {
    const response = await getTemplateList()
    myTemplates.value = response
  } catch (error) {
    ElMessage.error('加载模板列表失败')
  }
}

const loadSharedTemplates = async () => {
  try {
    const response = await getSharedTemplates()
    sharedTemplates.value = response
  } catch (error) {
    ElMessage.error('加载分享模板失败')
  }
}

const loadUsers = async () => {
  // TODO: 实现用户列表加载
  users.value = [
    { id: 1, username: 'user1' },
    { id: 2, username: 'user2' }
  ]
}

const handleShare = async () => {
  if (!form.value.template_id) {
    ElMessage.warning('请选择模板')
    return
  }
  if (!form.value.user_ids || form.value.user_ids.length === 0) {
    ElMessage.warning('请选择分享用户')
    return
  }

  sharing.value = true
  try {
    await shareTemplate(form.value.template_id, form.value.user_ids)
    ElMessage.success('分享成功')
    form.value.user_ids = []
  } catch (error) {
    ElMessage.error('分享失败')
  } finally {
    sharing.value = false
  }
}

const handleUse = (template) => {
  // TODO: 跳转到模板使用页面
  ElMessage.info(`使用模板: ${template.name}`)
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadMyTemplates()
  loadSharedTemplates()
  loadUsers()
})
</script>

<style scoped>
.template-share {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
```

- [ ] **步骤 4：添加路由**

```javascript
// frontend/src/router/index.js
{
  path: "/template-share",
  name: "TemplateShare",
  component: () => import("@/views/TemplateShare.vue"),
  meta: { requiresAuth: true }
}
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/services/template_service.py backend/app/api/templates.py frontend/src/views/TemplateShare.vue frontend/src/router/index.js
git commit -m "feat: 添加模板分享功能"
```

---

## 模块 3：版本控制功能

### 任务 6：实现版本控制功能

**文件：**
- 修改：`backend/app/services/template_service.py`
- 修改：`backend/app/api/templates.py`
- 创建：`frontend/src/views/TemplateVersionHistory.vue`
- 创建：`frontend/src/components/VersionDiff.vue`
- 修改：`frontend/src/router/index.js`

- [ ] **步骤 1：扩展模板服务**

```python
# backend/app/services/template_service.py
# 在 TemplateService 类中添加以下方法

def get_version_diff(self, template_id: int, version1: int, version2: int) -> dict:
    """获取两个版本之间的差异"""
    from app.models.template_version import TemplateVersion
    
    v1 = self.db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template_id,
        TemplateVersion.version == version1
    ).first()
    
    v2 = self.db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template_id,
        TemplateVersion.version == version2
    ).first()
    
    if not v1 or not v2:
        raise ValueError("版本不存在")
    
    # 简单的配置差异对比
    diff = {
        "version1": {
            "version": v1.version,
            "config": v1.config,
            "created_at": v1.created_at
        },
        "version2": {
            "version": v2.version,
            "config": v2.config,
            "created_at": v2.created_at
        },
        "changes": self._compare_configs(v1.config, v2.config)
    }
    
    return diff

def _compare_configs(self, config1: dict, config2: dict) -> dict:
    """比较两个配置的差异"""
    changes = {
        "added": [],
        "removed": [],
        "modified": []
    }
    
    # 比较顶层键
    keys1 = set(config1.keys())
    keys2 = set(config2.keys())
    
    changes["added"] = list(keys2 - keys1)
    changes["removed"] = list(keys1 - keys2)
    
    # 比较共同键的值
    common_keys = keys1 & keys2
    for key in common_keys:
        if config1[key] != config2[key]:
            changes["modified"].append({
                "key": key,
                "old": config1[key],
                "new": config2[key]
            })
    
    return changes
```

- [ ] **步骤 2：扩展模板 API**

```python
# backend/app/api/templates.py
# 添加以下路由

@router.get("/{template_id}/versions/diff")
async def get_version_diff(
    template_id: int,
    version1: int,
    version2: int,
    db: Session = Depends(get_db)
):
    """获取版本差异"""
    service = TemplateService(db)
    try:
        diff = service.get_version_diff(template_id, version1, version2)
        return diff
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

- [ ] **步骤 3：编写版本历史页面**

```vue
<!-- frontend/src/views/TemplateVersionHistory.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="template-version-history">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>模板版本历史</span>
            <el-button @click="handleBack">返回</el-button>
          </div>
        </template>

        <el-table :data="versions" style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="version" label="版本号" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_by" label="创建者" width="100" />
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="handleView(row)">
                查看
              </el-button>
              <el-button type="success" size="small" @click="handleRollback(row)">
                回滚
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="selectedVersion" style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>版本详情 - {{ selectedVersion.version }}</span>
          </div>
        </template>

        <pre>{{ JSON.stringify(selectedVersion.config, null, 2) }}</pre>
      </el-card>

      <el-card v-if="diffResult" style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>版本差异</span>
          </div>
        </template>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="新增" name="added">
            <el-tag
              v-for="item in diffResult.changes.added"
              :key="item"
              style="margin: 5px"
            >
              {{ item }}
            </el-tag>
          </el-tab-pane>
          <el-tab-pane label="删除" name="removed">
            <el-tag
              v-for="item in diffResult.changes.removed"
              :key="item"
              type="danger"
              style="margin: 5px"
            >
              {{ item }}
            </el-tag>
          </el-tab-pane>
          <el-tab-pane label="修改" name="modified">
            <div
              v-for="item in diffResult.changes.modified"
              :key="item.key"
              style="margin: 10px 0"
            >
              <el-tag>{{ item.key }}</el-tag>
              <div style="margin-top: 5px">
                <span style="color: #f56c66">旧值: {{ JSON.stringify(item.old) }}</span>
                <br />
                <span style="color: #67c23a">新值: {{ JSON.stringify(item.new) }}</span>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateVersions, rollbackTemplate } from '@/api/template'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

const router = useRouter()
const route = useRoute()

const versions = ref([])
const selectedVersion = ref(null)
const diffResult = ref(null)
const activeTab = ref('added')

const loadVersions = async () => {
  try {
    const response = await getTemplateVersions(route.params.id)
    versions.value = response
  } catch (error) {
    ElMessage.error('加载版本历史失败')
  }
}

const handleView = (version) => {
  selectedVersion.value = version
}

const handleRollback = async (version) => {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 ${version.version} 吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await rollbackTemplate(route.params.id, version.version)
    ElMessage.success('回滚成功')
    loadVersions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('回滚失败')
    }
  }
}

const handleBack = () => {
  router.push('/templates')
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadVersions()
})
</script>

<style scoped>
.template-version-history {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

pre {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>
```

- [ ] **步骤 4：添加路由**

```javascript
// frontend/src/router/index.js
{
  path: "/templates/:id/version-history",
  name: "TemplateVersionHistory",
  component: () => import("@/views/TemplateVersionHistory.vue"),
  meta: { requiresAuth: true }
}
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/services/template_service.py backend/app/api/templates.py frontend/src/views/TemplateVersionHistory.vue frontend/src/router/index.js
git commit -m "feat: 添加版本控制功能"
```

---

## 模块 4：性能优化

### 任务 7：实现缓存服务

**文件：**
- 创建：`backend/app/services/cache_service.py`
- 修改：`backend/app/services/query_service.py`

- [ ] **步骤 1：编写缓存服务**

```python
# backend/app/services/cache_service.py
import json
from typing import Optional, Any
import redis
from app.config import get_settings

settings = get_settings()

class CacheService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None
    
    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        try:
            return self.redis_client.setex(
                key,
                expire,
                json.dumps(value)
            )
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            return self.redis_client.delete(key) > 0
        except Exception:
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception:
            return False
    
    def generate_query_key(self, data_source_id: int, sql: str, params: dict) -> str:
        """生成查询缓存键"""
        import hashlib
        key_str = f"query:{data_source_id}:{sql}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def generate_template_key(self, template_id: int) -> str:
        """生成模板缓存键"""
        return f"template:{template_id}"
    
    def clear_query_cache(self, data_source_id: Optional[int] = None) -> int:
        """清除查询缓存"""
        try:
            if data_source_id:
                pattern = f"query:{data_source_id}:*"
            else:
                pattern = "query:*"
            
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception:
            return 0

# 全局缓存实例
cache_service = CacheService()
```

- [ ] **步骤 2：集成缓存到查询服务**

```python
# backend/app/services/query_service.py
# 在 QueryService 类中修改 execute_query 方法

from app.services.cache_service import cache_service

def execute_query(self, data_source_id: int, sql: str, params: dict) -> QueryResult:
    """执行 SQL 查询"""
    # 生成缓存键
    cache_key = cache_service.generate_query_key(data_source_id, sql, params)
    
    # 尝试从缓存获取
    cached_result = cache_service.get(cache_key)
    if cached_result:
        return QueryResult(**cached_result)
    
    # 执行查询
    # ... 原有查询逻辑 ...
    
    # 缓存结果（5分钟）
    cache_service.set(cache_key, result.dict(), expire=300)
    
    return result
```

- [ ] **步骤 3：验证缓存服务**

```bash
cd /home/zhou/myreport/backend
python3 -c "from app.services.cache_service import cache_service; print('✅ 缓存服务导入成功')"
```

- [ ] **步骤 4：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/services/cache_service.py backend/app/services/query_service.py
git commit -m "feat: 添加缓存服务"
```

---

### 任务 8：实现查询优化器

**文件：**
- 创建：`backend/app/utils/query_optimizer.py`
- 修改：`backend/app/services/query_service.py`

- [ ] **步骤 1：编写查询优化器**

```python
# backend/app/utils/query_optimizer.py
import re
from typing import List, Tuple

class QueryOptimizer:
    """SQL 查询优化器"""
    
    @staticmethod
    def optimize_query(sql: str) -> str:
        """优化 SQL 查询"""
        optimized = sql
        
        # 1. 添加 LIMIT 子句（如果没有）
        if not re.search(r'\bLIMIT\b', optimized, re.IGNORECASE):
            optimized += " LIMIT 100000"
        
        # 2. 移除不必要的空格
        optimized = re.sub(r'\s+', ' ', optimized)
        
        # 3. 移除注释
        optimized = re.sub(r'--.*?\n', '\n', optimized)
        optimized = re.sub(r'/\*.*?\*/', '', optimized, flags=re.DOTALL)
        
        # 4. 标准化关键字
        keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT']
        for keyword in keywords:
            optimized = re.sub(
                rf'\b{keyword}\b',
                keyword,
                optimized,
                flags=re.IGNORECASE
            )
        
        return optimized.strip()
    
    @staticmethod
    def validate_query(sql: str) -> Tuple[bool, str]:
        """验证 SQL 查询"""
        # 检查是否包含危险操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', sql, re.IGNORECASE):
                return False, f"不允许使用 {keyword} 操作"
        
        # 检查是否包含注释
        if '--' in sql or '/*' in sql:
            return False, "不允许使用 SQL 注释"
        
        # 检查是否包含分号（防止多语句）
        if ';' in sql:
            return False, "不允许使用多语句"
        
        return True, "验证通过"
    
    @staticmethod
    def estimate_query_cost(sql: str) -> int:
        """估算查询成本（简单实现）"""
        cost = 0
        
        # 根据关键字估算
        if 'JOIN' in sql.upper():
            cost += 100
        if 'GROUP BY' in sql.upper():
            cost += 50
        if 'ORDER BY' in sql.upper():
            cost += 30
        if 'HAVING' in sql.upper():
            cost += 20
        
        # 根据表数量估算
        from_count = sql.upper().count('FROM')
        cost += from_count * 10
        
        return cost
```

- [ ] **步骤 2：集成优化器到查询服务**

```python
# backend/app/services/query_service.py
from app.utils.query_optimizer import QueryOptimizer

def execute_query(self, data_source_id: int, sql: str, params: dict) -> QueryResult:
    """执行 SQL 查询"""
    # 验证查询
    is_valid, message = QueryOptimizer.validate_query(sql)
    if not is_valid:
        raise ValueError(message)
    
    # 优化查询
    optimized_sql = QueryOptimizer.optimize_query(sql)
    
    # 估算查询成本
    cost = QueryOptimizer.estimate_query_cost(optimized_sql)
    
    # 如果成本过高，建议异步处理
    if cost > 200:
        # TODO: 提示用户使用异步导出
        pass
    
    # 执行查询
    # ... 原有查询逻辑 ...
```

- [ ] **步骤 3：验证优化器**

```bash
cd /home/zhou/myreport/backend
python3 -c "from app.utils.query_optimizer import QueryOptimizer; print('✅ 查询优化器导入成功')"
```

- [ ] **步骤 4：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/utils/query_optimizer.py backend/app/services/query_service.py
git commit -m "feat: 添加查询优化器"
```

---

### 任务 9：实现限流中间件

**文件：**
- 创建：`backend/app/middleware/rate_limit.py`
- 修改：`backend/app/main.py`

- [ ] **步骤 1：编写限流中间件**

```python
# backend/app/middleware/rate_limit.py
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.max_requests = 100  # 每分钟最大请求数
        self.window = 60  # 时间窗口（秒）
    
    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        
        # 清理过期记录
        self.requests[key] = [
            timestamp for timestamp in self.requests[key]
            if now - timestamp < self.window
        ]
        
        # 检查是否超过限制
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        # 记录请求
        self.requests[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        """获取剩余请求数"""
        now = time.time()
        self.requests[key] = [
            timestamp for timestamp in self.requests[key]
            if now - timestamp < self.window
        ]
        return self.max_requests - len(self.requests[key])

# 全局限流器
rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    """限流中间件"""
    # 使用 IP 地址作为限流键
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    # 检查是否允许请求
    if not rate_limiter.is_allowed(key):
        remaining = rate_limiter.get_remaining(key)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "请求过于频繁，请稍后再试",
                "remaining": remaining
            }
        )
    
    # 添加限流信息到响应头
    response = await call_next(request)
    remaining = rate_limiter.get_remaining(key)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
    
    return response
```

- [ ] **步骤 2：注册限流中间件**

```python
# backend/app/main.py
from app.middleware.rate_limit import rate_limit_middleware

app.add_middleware(rate_limit_middleware)
```

- [ ] **步骤 3：验证限流中间件**

```bash
cd /home/zhou/myreport/backend
python3 -c "from app.middleware.rate_limit import rate_limiter; print('✅ 限流中间件导入成功')"
```

- [ ] **步骤 4：Commit**

```bash
cd /home/zhou/myreport
git add backend/app/middleware/rate_limit.py backend/app/main.py
git commit -m "feat: 添加限流中间件"
```

---

## 模块 5：测试和文档

### 任务 10：编写测试用例

**文件：**
- 创建：`backend/tests/test_async_export.py`
- 创建：`backend/tests/test_cache.py`
- 创建：`backend/tests/test_rate_limit.py`

- [ ] **步骤 1：编写异步导出测试**

```python
# backend/tests/test_async_export.py
import pytest
from app.services.async_export_service import AsyncExportService
from app.schemas.async_export import AsyncExportRequest

def test_create_export_task(db_session):
    """测试创建导出任务"""
    service = AsyncExportService(db_session)
    
    request = AsyncExportRequest(
        data_source_id=1,
        sql="SELECT * FROM users LIMIT 10",
        export_type="excel"
    )
    
    response = service.create_export_task(request, user_id=1)
    
    assert response.task_id is not None
    assert response.status == "PENDING"

def test_get_task_status(db_session):
    """测试获取任务状态"""
    service = AsyncExportService(db_session)
    
    # 先创建任务
    request = AsyncExportRequest(
        data_source_id=1,
        sql="SELECT * FROM users LIMIT 10",
        export_type="excel"
    )
    response = service.create_export_task(request, user_id=1)
    
    # 获取任务状态
    task = service.get_task_status(response.task_id)
    
    assert task is not None
    assert task.id == response.task_id
```

- [ ] **步骤 2：编写缓存测试**

```python
# backend/tests/test_cache.py
import pytest
from app.services.cache_service import CacheService

def test_cache_set_get():
    """测试缓存设置和获取"""
    cache = CacheService()
    
    cache.set("test_key", {"data": "test_value"})
    result = cache.get("test_key")
    
    assert result is not None
    assert result["data"] == "test_value"

def test_cache_delete():
    """测试缓存删除"""
    cache = CacheService()
    
    cache.set("test_key", {"data": "test_value"})
    cache.delete("test_key")
    result = cache.get("test_key")
    
    assert result is None
```

- [ ] **步骤 3：编写限流测试**

```python
# backend/tests/test_rate_limit.py
import pytest
from app.middleware.rate_limit import RateLimiter

def test_rate_limit():
    """测试限流功能"""
    limiter = RateLimiter()
    
    # 前100个请求应该被允许
    for i in range(100):
        assert limiter.is_allowed("test_key") is True
    
    # 第101个请求应该被拒绝
    assert limiter.is_allowed("test_key") is False

def test_rate_limit_remaining():
    """测试剩余请求数"""
    limiter = RateLimiter()
    
    # 发送10个请求
    for i in range(10):
        limiter.is_allowed("test_key")
    
    # 剩余请求数应该是90
    remaining = limiter.get_remaining("test_key")
    assert remaining == 90
```

- [ ] **步骤 4：运行测试**

```bash
cd /home/zhou/myreport/backend
pytest tests/test_async_export.py -v
pytest tests/test_cache.py -v
pytest tests/test_rate_limit.py -v
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add backend/tests/test_async_export.py backend/tests/test_cache.py backend/tests/test_rate_limit.py
git commit -m "test: 添加第三阶段功能测试"
```

---

### 任务 11：更新文档

**文件：**
- 修改：`README.md`
- 创建：`docs/async-export-guide.md`
- 创建：`docs/template-sharing-guide.md`
- 创建：`docs/performance-optimization-guide.md`

- [ ] **步骤 1：更新 README**

```markdown
# 自定义报表查询系统

## 第三阶段功能

### 异步导出
- 支持大数据量异步导出
- 实时任务进度跟踪
- 自动重试机制

### 模板分享
- 模板分享给其他用户
- 查看分享的模板
- 权限控制

### 版本控制
- 模板版本历史
- 版本对比
- 版本回滚

### 性能优化
- 查询结果缓存
- SQL 查询优化
- API 限流
```

- [ ] **步骤 2：创建异步导出指南**

```markdown
# 异步导出使用指南

## 功能介绍
异步导出功能支持大数据量的 Excel 和 PDF 导出，通过 Celery + Redis 实现任务队列管理。

## 使用方法
1. 在异步导出页面创建导出任务
2. 系统自动处理导出任务
3. 实时查看任务进度
4. 任务完成后下载文件

## 注意事项
- 大数据量导出建议使用异步模式
- 任务会在后台处理，可以关闭页面
- 导出文件保留7天
```

- [ ] **步骤 3：创建模板分享指南**

```markdown
# 模板分享使用指南

## 功能介绍
模板分享功能允许用户将创建的模板分享给其他用户使用。

## 使用方法
1. 在模板分享页面选择要分享的模板
2. 选择分享对象
3. 确认分享

## 权限说明
- 只有模板创建者可以分享模板
- 被分享用户可以查看和使用模板
- 不能修改分享的模板
```

- [ ] **步骤 4：创建性能优化指南**

```markdown
# 性能优化指南

## 缓存策略
- 查询结果自动缓存5分钟
- 模板配置自动缓存
- 支持手动清除缓存

## 查询优化
- 自动添加 LIMIT 子句
- SQL 语法验证
- 查询成本估算

## 限流策略
- 每分钟最多100次请求
- 超过限制返回429状态码
- 响应头包含限流信息
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add README.md docs/async-export-guide.md docs/template-sharing-guide.md docs/performance-optimization-guide.md
git commit -m "docs: 更新第三阶段文档"
```

---

## 模块 6：部署和验证

### 任务 12：启动 Celery Worker

**文件：**
- 创建：`scripts/start_celery.sh`

- [ ] **步骤 1：编写 Celery 启动脚本**

```bash
#!/bin/bash
# scripts/start_celery.sh

cd /home/zhou/myreport/backend

# 启动 Celery Worker
celery -A celery_config worker --loglevel=info --concurrency=4
```

- [ ] **步骤 2：启动 Redis**

```bash
sudo service redis-server start
```

- [ ] **步骤 3：启动 Celery Worker**

```bash
cd /home/zhou/myreport
chmod +x scripts/start_celery.sh
./scripts/start_celery.sh &
```

- [ ] **步骤 4：验证 Celery**

```bash
cd /home/zhou/myreport/backend
celery -A celery_config inspect active
```

- [ ] **步骤 5：Commit**

```bash
cd /home/zhou/myreport
git add scripts/start_celery.sh
git commit -m "feat: 添加 Celery 启动脚本"
```

---

### 任务 13：端到端测试

**文件：**
- 创建：`tests/e2e/test_phase3.py`

- [ ] **步骤 1：编写端到端测试**

```python
# tests/e2e/test_phase3.py
import pytest
import requests
import time

BASE_URL = "http://localhost:8000"

def test_async_export_flow():
    """测试异步导出完整流程"""
    # 1. 创建导出任务
    response = requests.post(
        f"{BASE_URL}/api/async-export/create",
        json={
            "data_source_id": 1,
            "sql": "SELECT * FROM users LIMIT 10",
            "export_type": "excel"
        }
    )
    assert response.status_code == 201
    task_id = response.json()["task_id"]
    
    # 2. 等待任务完成
    max_wait = 60
    for i in range(max_wait):
        response = requests.get(f"{BASE_URL}/api/async-export/task/{task_id}")
        assert response.status_code == 200
        task = response.json()
        
        if task["status"] in ["SUCCESS", "FAILED"]:
            break
        
        time.sleep(1)
    
    # 3. 验证任务状态
    assert task["status"] == "SUCCESS"
    assert task["file_path"] is not None

def test_template_share_flow():
    """测试模板分享完整流程"""
    # 1. 分享模板
    response = requests.post(
        f"{BASE_URL}/api/templates/1/share",
        json=[2, 3]
    )
    assert response.status_code == 200
    
    # 2. 获取分享的模板
    response = requests.get(f"{BASE_URL}/api/templates/shared")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) > 0

def test_cache_flow():
    """测试缓存功能"""
    # 1. 执行查询
    response = requests.post(
        f"{BASE_URL}/api/query/sql",
        json={
            "data_source_id": 1,
            "sql": "SELECT * FROM users LIMIT 10"
        }
    )
    assert response.status_code == 200
    
    # 2. 再次执行相同查询（应该从缓存获取）
    response = requests.post(
        f"{BASE_URL}/api/query/sql",
        json={
            "data_source_id": 1,
            "sql": "SELECT * FROM users LIMIT 10"
        }
    )
    assert response.status_code == 200
```

- [ ] **步骤 2：运行端到端测试**

```bash
cd /home/zhou/myreport
python3 tests/e2e/test_phase3.py
```

- [ ] **步骤 3：Commit**

```bash
cd /home/zhou/myreport
git add tests/e2e/test_phase3.py
git commit -m "test: 添加第三阶段端到端测试"
```

---

## 总结

### 完成的功能
1. ✅ 异步导出功能（Celery + Redis）
2. ✅ 模板分享功能
3. ✅ 版本控制功能
4. ✅ 性能优化（缓存、查询优化、限流）
5. ✅ 测试覆盖
6. ✅ 文档更新

### 技术亮点
- 异步任务处理
- 实时进度跟踪
- 智能缓存策略
- SQL 查询优化
- API 限流保护

### 下一步建议
1. 添加更多图表类型
2. 实现数据源连接池
3. 添加审计日志
4. 实现数据脱敏
5. 添加更多导出格式

---

**计划已完成并保存到 `docs/superpowers/plans/2025-04-21-custom-report-system-phase3.md`。**

**两种执行方式：**

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

**选哪种方式？**
