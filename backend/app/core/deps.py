"""Common FastAPI dependencies — shared across API routes."""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.models.data_source import DataSource
from app.services.data_source_service import DataSourceService


def get_data_source_or_404(
    data_source_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> DataSource:
    """获取当前用户可访问的数据源。

    Usage:
        @router.get("/{data_source_id}")
        async def handler(ds: DataSource = Depends(get_data_source_or_404)):
            ...
    """
    return DataSourceService(db).require_access(data_source_id, current_user_id)


def get_active_data_source_or_404(
    data_source_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> DataSource:
    """获取活动数据源，不存在或未激活则抛 404。"""
    ds = DataSourceService(db).require_access(data_source_id, current_user_id)
    if not ds.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源已禁用",
        )
    return ds
