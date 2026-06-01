"""Semantic metric metadata API."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.schemas.semantic_metric import (
    SemanticMetricCreate,
    SemanticMetricPermissionCreate,
    SemanticMetricPermissionResponse,
    SemanticMetricQueryRequest,
    SemanticMetricQueryResponse,
    SemanticMetricRollbackRequest,
    SemanticMetricResponse,
    SemanticMetricSqlPreview,
    SemanticMetricUpdate,
    SemanticMetricVersionResponse,
)
from app.services.semantic_metric_query_service import SemanticMetricQueryService
from app.utils.sql_validator import SQLValidator
from app.utils.sql_normalizer import strip_trailing_semicolon

router = APIRouter(prefix="/api/semantic-metrics", tags=["语义指标"])


def _validate_metric_sql(sql: str) -> None:
    sql = strip_trailing_semicolon(sql)
    is_valid, message = SQLValidator.validate(sql)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _is_admin(user: User) -> bool:
    return bool(user.role and user.role.name == "admin")


def _get_visible_metric_or_404(repo: SemanticMetricRepository, metric_id: int, user: User):
    metric = repo.get_visible_by_id(
        metric_id,
        user_id=user.id,
        is_admin=_is_admin(user),
    )
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")
    return metric


def _get_editable_metric_or_404(repo: SemanticMetricRepository, metric_id: int, user: User):
    metric = repo.get_editable_by_id(
        metric_id,
        user_id=user.id,
        is_admin=_is_admin(user),
    )
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")
    return metric


def _get_manageable_metric_or_404(repo: SemanticMetricRepository, metric_id: int, user: User):
    metric = repo.get_by_id(metric_id)
    if not metric or (not _is_admin(user) and metric.created_by != user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")
    return metric


@router.post("", response_model=SemanticMetricResponse, status_code=status.HTTP_201_CREATED)
async def create_metric(
    payload: SemanticMetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    if repo.get_by_key(payload.metric_key):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="metric_key 已存在")

    if not DataSourceRepository(db).get_by_id(payload.data_source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据源不存在")

    _validate_metric_sql(payload.base_sql)
    return repo.create(payload.model_dump(), current_user.id)


@router.get("", response_model=list[SemanticMetricResponse])
async def list_metrics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SemanticMetricRepository(db).list_visible(
        current_user.id,
        is_admin=_is_admin(current_user),
        skip=skip,
        limit=limit,
        active_only=active_only,
    )


@router.post("/query/preview", response_model=SemanticMetricSqlPreview)
async def preview_metric_query(
    payload: SemanticMetricQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _, preview = SemanticMetricQueryService(db).preview_sql(
            payload,
            user_id=current_user.id,
            is_admin=_is_admin(current_user),
        )
        return preview
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/query/execute", response_model=SemanticMetricQueryResponse)
async def execute_metric_query(
    payload: SemanticMetricQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        metric, query_response = SemanticMetricQueryService(db).execute(
            payload,
            user_id=current_user.id,
            is_admin=_is_admin(current_user),
        )
        return SemanticMetricQueryResponse(metric=metric, query=query_response)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{metric_id}/versions", response_model=list[SemanticMetricVersionResponse])
async def list_metric_versions(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    _get_visible_metric_or_404(repo, metric_id, current_user)
    return repo.list_versions(metric_id)


@router.post("/{metric_id}/rollback", response_model=SemanticMetricResponse)
async def rollback_metric(
    metric_id: int,
    payload: SemanticMetricRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    metric = _get_editable_metric_or_404(repo, metric_id, current_user)
    version = repo.get_version(metric_id, payload.version_number)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标版本不存在")

    metric_key = version.snapshot["metric_key"]
    existing = repo.get_by_key(metric_key)
    if existing and existing.id != metric_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="metric_key 已存在")

    if not DataSourceRepository(db).get_by_id(version.snapshot["data_source_id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据源不存在")
    _validate_metric_sql(version.snapshot["base_sql"])

    return repo.rollback_to_version(metric, version, user_id=current_user.id)


@router.get("/{metric_id}/permissions", response_model=list[SemanticMetricPermissionResponse])
async def list_metric_permissions(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    _get_manageable_metric_or_404(repo, metric_id, current_user)
    return repo.list_permissions(metric_id)


@router.post("/{metric_id}/permissions", response_model=SemanticMetricPermissionResponse)
async def grant_metric_permission(
    metric_id: int,
    payload: SemanticMetricPermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    metric = _get_manageable_metric_or_404(repo, metric_id, current_user)
    if payload.user_id == metric.created_by:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="指标负责人无需授权")
    if not db.query(User).filter(User.id == payload.user_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="授权用户不存在")
    return repo.grant_permission(
        metric_id=metric_id,
        user_id=payload.user_id,
        permission_level=payload.permission_level,
        granted_by=current_user.id,
    )


@router.delete("/{metric_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_metric_permission(
    metric_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    _get_manageable_metric_or_404(repo, metric_id, current_user)
    repo.revoke_permission(metric_id, user_id)


@router.get("/{metric_id}", response_model=SemanticMetricResponse)
async def get_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_visible_metric_or_404(SemanticMetricRepository(db), metric_id, current_user)


@router.put("/{metric_id}", response_model=SemanticMetricResponse)
async def update_metric(
    metric_id: int,
    payload: SemanticMetricUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    metric = _get_editable_metric_or_404(repo, metric_id, current_user)

    data = payload.model_dump(exclude_unset=True)
    if "metric_key" in data:
        existing = repo.get_by_key(data["metric_key"])
        if existing and existing.id != metric_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="metric_key 已存在")

    if "data_source_id" in data and not DataSourceRepository(db).get_by_id(data["data_source_id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="数据源不存在")

    if "base_sql" in data:
        _validate_metric_sql(data["base_sql"])

    return repo.update(metric, data, user_id=current_user.id)


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SemanticMetricRepository(db)
    metric = _get_manageable_metric_or_404(repo, metric_id, current_user)
    repo.delete(metric)
