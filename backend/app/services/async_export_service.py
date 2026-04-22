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
