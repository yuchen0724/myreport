# backend/app/api/async_export.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.async_export import AsyncExportRequest, AsyncExportResponse, ExportTaskStatus
from app.services.async_export_service import AsyncExportService

router = APIRouter(prefix="/api/async-export", tags=["异步导出"])

@router.post("/create", response_model=AsyncExportResponse, status_code=status.HTTP_201_CREATED)
async def create_export_task(
    request: AsyncExportRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
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
        sql=task.sql,  # 添加SQL字段
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
    current_user_id: int = Depends(get_current_user_id)
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
            sql=task.sql,  # 添加SQL字段
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
