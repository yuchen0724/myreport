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
    """获取数据源详情（不包含密码）"""
    ds_service = DataSourceService(db)
    ds = ds_service.get_data_source(ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    return ds


@router.get("/{ds_id}/password")
async def get_data_source_password(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取数据源解密密码

    仅所有者或管理员可访问。此接口有审计日志记录。
    """
    ds_service = DataSourceService(db)
    from app.models.data_source import DataSource
    db_ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not db_ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )

    # 权限检查：所有者或管理员
    from app.models.user import User
    user = db.query(User).filter(User.id == current_user_id).first()
    is_owner = db_ds.created_by and db_ds.created_by == current_user_id
    is_admin = user and user.role_id == 1
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限查看此数据源的密码",
        )

    from app.core.security import decrypt_password
    return {
        "id": db_ds.id,
        "name": db_ds.name,
        "password_decrypted": decrypt_password(db_ds.password_encrypted),
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
    return ds_service.update_data_source(ds_id, ds_data, current_user_id)


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    ds_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """删除数据源"""
    ds_service = DataSourceService(db)
    ds_service.delete_data_source(ds_id, current_user_id)


@router.post("/test", response_model=DataSourceTestResponse)
async def test_data_source_connection(
    request: DataSourceTestRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """测试数据源连接"""
    ds_service = DataSourceService(db)
    return ds_service.test_connection(request)
