# backend/app/services/template_service.py
from typing import List, Optional, Dict, Any
import json
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse, TemplateVersionResponse, TemplateShareRequest, SharedTemplateResponse, PaginatedTemplateResponse
from app.models.template import Template
from app.models.template_version import TemplateVersion
from app.models.template_share import TemplateShare
from app.models.user import User
from app.repositories.template_repository import TemplateRepository
from app.repositories.template_version_repository import TemplateVersionRepository
from app.exceptions import AuthorizationError, NotFoundError
from sqlalchemy.orm import Session

class TemplateService:
    """模板服务"""

    def __init__(self, db: Session):
        self.db = db
        self.template_repo = TemplateRepository(db)
        self.version_repo = TemplateVersionRepository(db)

    def _require_template(self, template_id: int) -> Template:
        """获取模板，不存在则抛出 NotFoundError"""
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise NotFoundError(f"模板不存在 (id={template_id})")
        return template

    def _check_owner(self, template: Template, user_id: int) -> None:
        """校验当前用户是否为模板所有者，不是则抛出 AuthorizationError"""
        if template.created_by != user_id:
            raise AuthorizationError("您没有权限操作此模板")

    def require_view_access(self, template_id: int, user_id: int) -> Template:
        """返回当前用户可见的模板，否则拒绝访问。"""
        template = self._require_template(template_id)
        if template.created_by == user_id or template.is_public:
            return template

        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.role and user.role.name == "admin":
            return template

        shared = self.db.query(TemplateShare).filter(
            TemplateShare.template_id == template_id,
            TemplateShare.user_id == user_id,
        ).first()
        if shared:
            return template
        raise AuthorizationError("您没有权限查看此模板")

    def create_template(self, template_data: TemplateCreate, user_id: int) -> TemplateResponse:
        """
        创建模板

        Args:
            template_data: 模板数据
            user_id: 用户 ID

        Returns:
            模板响应

        Raises:
            ValueError: 配置中缺少必要字段
        """
        config = template_data.config
        if not config.get("data_source_id"):
            raise ValueError("模板配置缺少 data_source_id（数据源ID）")
        if not config.get("sql"):
            raise ValueError("模板配置缺少 sql（SQL语句）")
        # 创建模板
        template = Template(
            name=template_data.name,
            description=template_data.description,
            config=json.dumps(template_data.config),
            is_public=template_data.is_public,
            created_by=user_id,
            version=1
        )

        created_template = self.template_repo.create(template)

        # 创建版本记录
        version = TemplateVersion(
            template_id=created_template.id,
            version=1,
            config=json.dumps(template_data.config),
            created_by=user_id
        )
        self.version_repo.create(version)
        self.db.commit()

        return TemplateResponse(
            id=created_template.id,
            name=created_template.name,
            description=created_template.description,
            config=json.loads(created_template.config),
            version=created_template.version,
            is_public=created_template.is_public,
            created_by=created_template.created_by,
            created_at=created_template.created_at,
            updated_at=created_template.updated_at
        )

    def get_template(self, template_id: int, user_id: int) -> Optional[TemplateResponse]:
        """
        获取模板

        Args:
            template_id: 模板 ID

        Returns:
            模板响应
        """
        try:
            template = self.require_view_access(template_id, user_id)
        except NotFoundError:
            return None

        return TemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            config=json.loads(template.config),
            version=template.version,
            is_public=template.is_public,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at
        )

    def get_templates(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[TemplateResponse]:
        """
        获取模板列表（无分页元数据，兼容旧调用）

        Args:
            user_id: 用户 ID（可选）
            skip: 跳过数量
            limit: 限制数量

        Returns:
            模板响应列表
        """
        templates = self.template_repo.get_all(user_id, skip=skip, limit=limit)

        return [
            TemplateResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                config=json.loads(t.config),
                version=t.version,
                is_public=t.is_public,
                created_by=t.created_by,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            for t in templates
        ]

    def get_templates_paginated(self, user_id: Optional[int] = None, page: int = 1, page_size: int = 100) -> PaginatedTemplateResponse:
        """
        获取模板列表（带分页元数据）

        Args:
            user_id: 用户 ID（可选）
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            分页模板响应，包含 items / total / page / page_size / total_pages
        """
        skip = (page - 1) * page_size
        total = self.template_repo.count(user_id)
        templates = self.template_repo.get_all(user_id, skip=skip, limit=page_size)

        items = [
            TemplateResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                config=json.loads(t.config),
                version=t.version,
                is_public=t.is_public,
                created_by=t.created_by,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            for t in templates
        ]
        total_pages = max(1, (total + page_size - 1) // page_size)
        return PaginatedTemplateResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def update_template(self, template_id: int, template_data: TemplateUpdate, user_id: int) -> Optional[TemplateResponse]:
        """
        更新模板

        Args:
            template_id: 模板 ID
            template_data: 模板数据
            user_id: 用户 ID

        Returns:
            模板响应

        Raises:
            NotFoundError: 模板不存在
            AuthorizationError: 无操作权限
            ValueError: 配置中缺少必要字段
        """
        template = self._require_template(template_id)
        self._check_owner(template, user_id)

        # 更新模板
        if template_data.name is not None:
            template.name = template_data.name
        if template_data.description is not None:
            template.description = template_data.description
        if template_data.config is not None:
            config = template_data.config
            if not config.get("data_source_id"):
                raise ValueError("模板配置缺少 data_source_id（数据源ID）")
            if not config.get("sql"):
                raise ValueError("模板配置缺少 sql（SQL语句）")
            template.config = json.dumps(template_data.config)
        if template_data.is_public is not None:
            template.is_public = template_data.is_public

        # 增加版本号
        template.version += 1

        updated_template = self.template_repo.update(template)

        # 创建新版本记录
        version = TemplateVersion(
            template_id=updated_template.id,
            version=updated_template.version,
            config=json.dumps(template_data.config),
            created_by=user_id
        )
        self.version_repo.create(version)
        self.db.commit()

        return TemplateResponse(
            id=updated_template.id,
            name=updated_template.name,
            description=updated_template.description,
            config=json.loads(updated_template.config),
            version=updated_template.version,
            is_public=updated_template.is_public,
            created_by=updated_template.created_by,
            created_at=updated_template.created_at,
            updated_at=updated_template.updated_at
        )

    def delete_template(self, template_id: int, user_id: int) -> bool:
        """
        删除模板

        Args:
            template_id: 模板 ID
            user_id: 用户 ID

        Returns:
            是否成功

        Raises:
            NotFoundError: 模板不存在
            AuthorizationError: 无操作权限
        """
        template = self._require_template(template_id)
        self._check_owner(template, user_id)
        result = self.template_repo.delete(template)
        self.db.commit()
        return result

    def get_template_versions(self, template_id: int, user_id: int) -> List[TemplateVersionResponse]:
        """
        获取模板版本列表

        Args:
            template_id: 模板 ID

        Returns:
            版本响应列表
        """
        self.require_view_access(template_id, user_id)
        versions = self.version_repo.get_by_template_id(template_id)

        return [
            TemplateVersionResponse(
                id=v.id,
                template_id=v.template_id,
                version=v.version,
                config=json.loads(v.config) if v.config else {},
                created_by=v.created_by,
                created_at=v.created_at
            )
            for v in versions
        ]

    def rollback_template(self, template_id: int, version: int, user_id: int) -> Optional[TemplateResponse]:
        """
        回滚模板到指定版本

        Args:
            template_id: 模板 ID
            version: 版本号
            user_id: 用户 ID

        Returns:
            模板响应

        Raises:
            NotFoundError: 模板或版本不存在
            AuthorizationError: 无操作权限
        """
        # 获取指定版本
        target_version = self.version_repo.get_by_version(template_id, version)
        if not target_version:
            raise NotFoundError(f"版本不存在 (template_id={template_id}, version={version})")

        # 获取当前模板
        template = self._require_template(template_id)
        self._check_owner(template, user_id)

        # 更新模板配置
        template.config = target_version.config
        template.version += 1

        updated_template = self.template_repo.update(template)

        # 创建新版本记录
        new_version = TemplateVersion(
            template_id=updated_template.id,
            version=updated_template.version,
            config=target_version.config,
            created_by=user_id
        )
        self.version_repo.create(new_version)
        self.db.commit()

        return TemplateResponse(
            id=updated_template.id,
            name=updated_template.name,
            description=updated_template.description,
            config=json.loads(updated_template.config),
            version=updated_template.version,
            is_public=updated_template.is_public,
            created_by=updated_template.created_by,
            created_at=updated_template.created_at,
            updated_at=updated_template.updated_at
        )

    def share_template(self, template_id: int, share_request: TemplateShareRequest, shared_by: int) -> bool:
        """
        分享模板

        Args:
            template_id: 模板 ID
            share_request: 分享请求
            shared_by: 分享者 ID

        Returns:
            是否成功

        Raises:
            NotFoundError: 模板不存在
            AuthorizationError: 无操作权限
        """
        template = self._require_template(template_id)
        self._check_owner(template, shared_by)

        # 删除旧的分享记录
        self.db.query(TemplateShare).filter(
            TemplateShare.template_id == template_id
        ).delete()

        # 创建新的分享记录
        for user_id in share_request.user_ids:
            share = TemplateShare(
                template_id=template_id,
                user_id=user_id,
                shared_by=shared_by
            )
            self.db.add(share)

        self.db.commit()
        return True

    def get_shared_templates(self, user_id: int, skip: int = 0, limit: int = 100) -> List[SharedTemplateResponse]:
        """
        获取分享给用户的模板列表

        Args:
            user_id: 用户 ID
            skip: 跳过数量
            limit: 限制数量

        Returns:
            模板响应列表
        """
        # 查询分享记录和模板信息
        shares = self.db.query(TemplateShare, Template, User).join(
            Template, TemplateShare.template_id == Template.id
        ).join(
            User, TemplateShare.shared_by == User.id
        ).filter(
            TemplateShare.user_id == user_id
        ).order_by(TemplateShare.shared_at.desc()).offset(skip).limit(limit).all()

        return [
            SharedTemplateResponse(
                id=template.id,
                name=template.name,
                description=template.description,
                config=json.loads(template.config),
                version=template.version,
                is_public=template.is_public,
                created_by=template.created_by,
                created_at=template.created_at,
                updated_at=template.updated_at,
                shared_by=share.shared_by,
                shared_by_username=user.username,
                shared_at=share.shared_at
            )
            for share, template, user in shares
        ]

    def get_template_shares(self, template_id: int, user_id: int) -> List[dict]:
        """
        获取模板的分享用户列表

        Args:
            template_id: 模板 ID
            user_id: 请求用户 ID

        Returns:
            用户信息列表（包含用户ID、用户名、邮箱、分享时间）

        Raises:
            NotFoundError: 模板不存在
            AuthorizationError: 无操作权限
        """
        template = self._require_template(template_id)
        self._check_owner(template, user_id)
        shares = self.db.query(TemplateShare, User).join(
            User, TemplateShare.user_id == User.id
        ).filter(
            TemplateShare.template_id == template_id
        ).all()

        return [
            {
                "user_id": share.user_id,
                "username": user.username,
                "email": user.email,
                "shared_at": share.shared_at
            }
            for share, user in shares
        ]

    def unshare_template(self, template_id: int, target_user_id: int, current_user_id: int) -> bool:
        """
        取消分享模板

        Args:
            template_id: 模板 ID
            target_user_id: 被取消分享的用户 ID
            current_user_id: 当前操作用户 ID

        Returns:
            是否成功

        Raises:
            NotFoundError: 模板或分享记录不存在
            AuthorizationError: 无操作权限
        """
        template = self._require_template(template_id)
        self._check_owner(template, current_user_id)
        share = self.db.query(TemplateShare).filter(
            TemplateShare.template_id == template_id,
            TemplateShare.user_id == target_user_id
        ).first()

        if not share:
            return False

        self.db.delete(share)
        self.db.commit()
        return True

    def get_version_diff(self, template_id: int, version1: int, version2: int, user_id: int) -> dict:
        """
        获取两个版本之间的差异

        Args:
            template_id: 模板 ID
            version1: 版本号 1
            version2: 版本号 2

        Returns:
            版本差异
        """
        self.require_view_access(template_id, user_id)
        v1 = self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == version1
        ).first()

        v2 = self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == version2
        ).first()

        if not v1 or not v2:
            missing = version2 if v1 else version1
            raise NotFoundError(
                f"版本不存在 (template_id={template_id}, version={missing})"
            )

        # 解析配置
        config1 = json.loads(v1.config) if isinstance(v1.config, str) else v1.config
        config2 = json.loads(v2.config) if isinstance(v2.config, str) else v2.config

        # 简单的配置差异对比
        diff = {
            "version1": {
                "version": v1.version,
                "config": config1,
                "created_at": v1.created_at.isoformat()
            },
            "version2": {
                "version": v2.version,
                "config": config2,
                "created_at": v2.created_at.isoformat()
            },
            "changes": self._compare_configs(config1, config2)
        }

        return diff

    def _compare_configs(self, config1: dict, config2: dict) -> dict:
        """
        比较两个配置的差异

        Args:
            config1: 配置 1
            config2: 配置 2

        Returns:
            差异
        """
        changes = {
            "added": [],
            "removed": [],
            "modified": []
        }

        # 比较顶层键
        keys1 = set(config1.keys()) if config1 else set()
        keys2 = set(config2.keys()) if config2 else set()

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
