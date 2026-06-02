"""Common FastAPI dependencies — shared across API routes."""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.data_source import DataSource


def get_data_source_or_404(
    data_source_id: int,
    db: Session = Depends(get_db),
) -> DataSource:
    """获取数据源，不存在则抛 404。

    Usage:
        @router.get("/{data_source_id}")
        async def handler(ds: DataSource = Depends(get_data_source_or_404)):
            ...
    """
    ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    return ds


def get_active_data_source_or_404(
    data_source_id: int,
    db: Session = Depends(get_db),
) -> DataSource:
    """获取活动数据源，不存在或未激活则抛 404。"""
    ds = get_data_source_or_404(data_source_id, db=db)
    if not ds.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源已禁用",
        )
    return ds
