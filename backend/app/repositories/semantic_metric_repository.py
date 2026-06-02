from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.semantic_metric import SemanticMetric, SemanticMetricPermission, SemanticMetricVersion


SNAPSHOT_FIELDS = [
    "metric_key",
    "name",
    "description",
    "data_source_id",
    "base_sql",
    "metric_expression",
    "dimensions",
    "time_column",
    "is_active",
]


class SemanticMetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, metric_id: int) -> Optional[SemanticMetric]:
        return self.db.query(SemanticMetric).filter(SemanticMetric.id == metric_id).first()

    def get_by_key(self, metric_key: str) -> Optional[SemanticMetric]:
        return self.db.query(SemanticMetric).filter(SemanticMetric.metric_key == metric_key).first()

    def get_visible_by_id(self, metric_id: int, user_id: int, is_admin: bool = False) -> Optional[SemanticMetric]:
        query = self.db.query(SemanticMetric).filter(SemanticMetric.id == metric_id)
        if not is_admin:
            query = query.filter(self._visible_filter(user_id))
        return query.first()

    def get_editable_by_id(self, metric_id: int, user_id: int, is_admin: bool = False) -> Optional[SemanticMetric]:
        query = self.db.query(SemanticMetric).filter(SemanticMetric.id == metric_id)
        if not is_admin:
            query = query.filter(self._editable_filter(user_id))
        return query.first()

    def get_visible_by_key(
        self,
        metric_key: str,
        user_id: int,
        is_admin: bool = False,
        active_only: bool = False,
    ) -> Optional[SemanticMetric]:
        query = self.db.query(SemanticMetric).filter(SemanticMetric.metric_key == metric_key)
        if not is_admin:
            query = query.filter(self._visible_filter(user_id))
        if active_only:
            query = query.filter(SemanticMetric.is_active.is_(True))
        return query.first()

    def list(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> list[SemanticMetric]:
        query = self.db.query(SemanticMetric).order_by(SemanticMetric.id.desc())
        if active_only:
            query = query.filter(SemanticMetric.is_active.is_(True))
        return query.offset(skip).limit(limit).all()

    def list_visible(
        self,
        user_id: int,
        is_admin: bool = False,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> list[SemanticMetric]:
        query = self.db.query(SemanticMetric).order_by(SemanticMetric.id.desc())
        if not is_admin:
            query = query.filter(self._visible_filter(user_id))
        if active_only:
            query = query.filter(SemanticMetric.is_active.is_(True))
        return query.offset(skip).limit(limit).all()

    def list_visible_for_data_source(
        self,
        data_source_id: int,
        user_id: int,
        is_admin: bool = False,
        limit: int = 20,
        active_only: bool = True,
    ) -> list[SemanticMetric]:
        query = (
            self.db.query(SemanticMetric)
            .filter(SemanticMetric.data_source_id == data_source_id)
            .order_by(SemanticMetric.id.desc())
        )
        if not is_admin:
            query = query.filter(self._visible_filter(user_id))
        if active_only:
            query = query.filter(SemanticMetric.is_active.is_(True))
        return query.limit(limit).all()

    def list_permissions(self, metric_id: int) -> list[SemanticMetricPermission]:
        return (
            self.db.query(SemanticMetricPermission)
            .filter(SemanticMetricPermission.metric_id == metric_id)
            .order_by(SemanticMetricPermission.id.asc())
            .all()
        )

    def get_permission(self, metric_id: int, user_id: int) -> Optional[SemanticMetricPermission]:
        return (
            self.db.query(SemanticMetricPermission)
            .filter(
                SemanticMetricPermission.metric_id == metric_id,
                SemanticMetricPermission.user_id == user_id,
            )
            .first()
        )

    def grant_permission(
        self,
        metric_id: int,
        user_id: int,
        permission_level: str,
        granted_by: int,
    ) -> SemanticMetricPermission:
        permission = self.get_permission(metric_id, user_id)
        if permission:
            permission.permission_level = permission_level
            permission.granted_by = granted_by
        else:
            permission = SemanticMetricPermission(
                metric_id=metric_id,
                user_id=user_id,
                permission_level=permission_level,
                granted_by=granted_by,
            )
            self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def revoke_permission(self, metric_id: int, user_id: int) -> bool:
        permission = self.get_permission(metric_id, user_id)
        if not permission:
            return False
        self.db.delete(permission)
        self.db.flush()
        return True

    def create(self, data: dict, user_id: int) -> SemanticMetric:
        metric = SemanticMetric(**data, created_by=user_id)
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        self.create_version(metric, user_id=user_id, change_summary="创建指标")
        return metric

    def update(
        self,
        metric: SemanticMetric,
        data: dict,
        user_id: int | None = None,
        change_summary: str | None = None,
    ) -> SemanticMetric:
        for key, value in data.items():
            if hasattr(metric, key):
                setattr(metric, key, value)
        self.db.flush()
        self.db.refresh(metric)
        if data and user_id is not None:
            self.create_version(metric, user_id=user_id, change_summary=change_summary or "更新指标")
        return metric

    def delete(self, metric: SemanticMetric) -> None:
        self.db.delete(metric)
        self.db.flush()

    def list_versions(self, metric_id: int) -> list[SemanticMetricVersion]:
        return (
            self.db.query(SemanticMetricVersion)
            .filter(SemanticMetricVersion.metric_id == metric_id)
            .order_by(SemanticMetricVersion.version_number.desc())
            .all()
        )

    def get_version(self, metric_id: int, version_number: int) -> Optional[SemanticMetricVersion]:
        return (
            self.db.query(SemanticMetricVersion)
            .filter(
                SemanticMetricVersion.metric_id == metric_id,
                SemanticMetricVersion.version_number == version_number,
            )
            .first()
        )

    def create_version(
        self,
        metric: SemanticMetric,
        user_id: int,
        change_summary: str | None = None,
    ) -> SemanticMetricVersion:
        version = SemanticMetricVersion(
            metric_id=metric.id,
            version_number=self._next_version_number(metric.id),
            snapshot=self._build_snapshot(metric),
            change_summary=change_summary,
            created_by=user_id,
        )
        self.db.add(version)
        self.db.flush()
        self.db.refresh(version)
        return version

    def rollback_to_version(
        self,
        metric: SemanticMetric,
        version: SemanticMetricVersion,
        user_id: int,
    ) -> SemanticMetric:
        for key in SNAPSHOT_FIELDS:
            setattr(metric, key, version.snapshot[key])
        self.db.flush()
        self.db.refresh(metric)
        self.create_version(
            metric,
            user_id=user_id,
            change_summary=f"回滚到 v{version.version_number}",
        )
        return metric

    def _next_version_number(self, metric_id: int) -> int:
        latest = (
            self.db.query(SemanticMetricVersion.version_number)
            .filter(SemanticMetricVersion.metric_id == metric_id)
            .order_by(SemanticMetricVersion.version_number.desc())
            .first()
        )
        return (latest[0] + 1) if latest else 1

    def _build_snapshot(self, metric: SemanticMetric) -> dict:
        return {field: getattr(metric, field) for field in SNAPSHOT_FIELDS}

    def _visible_filter(self, user_id: int):
        shared_metric_ids = (
            self.db.query(SemanticMetricPermission.metric_id)
            .filter(SemanticMetricPermission.user_id == user_id)
        )
        return or_(
            SemanticMetric.created_by == user_id,
            SemanticMetric.id.in_(shared_metric_ids),
        )

    def _editable_filter(self, user_id: int):
        editable_metric_ids = (
            self.db.query(SemanticMetricPermission.metric_id)
            .filter(
                SemanticMetricPermission.user_id == user_id,
                SemanticMetricPermission.permission_level == "editor",
            )
        )
        return or_(
            SemanticMetric.created_by == user_id,
            SemanticMetric.id.in_(editable_metric_ids),
        )
