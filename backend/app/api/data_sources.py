from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    DataSourceTestRequest,
    DataSourceTestResponse,
)
from app.services.data_source_service import DataSourceService

router = APIRouter(prefix="/api/datasources", tags=["数据源管理"])


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    ds_data: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """创建数据源"""
    ds_service = DataSourceService(db)
    try:
        return ds_service.create_data_source(ds_data, current_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[DataSourceResponse])
async def list_data_sources(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """列出数据源"""
    ds_service = DataSourceService(db)
    return ds_service.list_data_sources(current_user_id, skip, limit)


@router.get("/{ds_id}", response_model=DataSourceResponse)
async def get_data_source(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取数据源详情（包含解密密码，方便编辑测试）"""
    ds_service = DataSourceService(db)
    ds = ds_service.get_data_source(ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    # 返回包含解密密码的响应
    from app.core.security import decrypt_password
    from sqlalchemy import select
    from app.models.data_source import DataSource
    
    # 重新查询获取原始数据库对象
    db_ds = db.execute(select(DataSource).where(DataSource.id == ds_id)).scalar_one_or_none()
    if not db_ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    
    return {
        "id": db_ds.id,
        "name": db_ds.name,
        "type": db_ds.type,
        "host": db_ds.host,
        "port": db_ds.port,
        "database": db_ds.database,
        "username": db_ds.username,
        "password_decrypted": decrypt_password(db_ds.password_encrypted),
        "is_active": db_ds.is_active,
        "created_by": db_ds.created_by,
        "created_at": db_ds.created_at,
        "updated_at": db_ds.updated_at,
    }


@router.put("/{ds_id}", response_model=DataSourceResponse)
async def update_data_source(
    ds_id: int,
    ds_data: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """更新数据源"""
    ds_service = DataSourceService(db)
    ds = ds_service.update_data_source(ds_id, ds_data)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    return ds


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """删除数据源"""
    ds_service = DataSourceService(db)
    success = ds_service.delete_data_source(ds_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )


@router.post("/test", response_model=DataSourceTestResponse)
async def test_data_source_connection(
    request: DataSourceTestRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """测试数据源连接"""
    ds_service = DataSourceService(db)
    return ds_service.test_connection(request)
