# backend/app/services/template_service.py
from typing import List, Optional, Dict, Any
import json
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse, TemplateVersionResponse, TemplateShareRequest, SharedTemplateResponse
from app.models.template import Template
from app.models.template_version import TemplateVersion
from app.models.template_share import TemplateShare
from app.repositories.template_repository import TemplateRepository
from app.repositories.template_version_repository import TemplateVersionRepository
from sqlalchemy.orm import Session

class TemplateService:
    """模板服务"""

    def __init__(self, db: Session):
        self.db = db
        self.template_repo = TemplateRepository(db)
        self.version_repo = TemplateVersionRepository(db)

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

    def get_template(self, template_id: int) -> Optional[TemplateResponse]:
        """
        获取模板

        Args:
            template_id: 模板 ID

        Returns:
            模板响应
        """
        template = self.template_repo.get_by_id(template_id)
        if not template:
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

    def get_templates(self, user_id: Optional[int] = None) -> List[TemplateResponse]:
        """
        获取模板列表

        Args:
            user_id: 用户 ID（可选）

        Returns:
            模板响应列表
        """
        templates = self.template_repo.get_all(user_id)

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
            ValueError: 配置中缺少必要字段
        """
        template = self.template_repo.get_by_id(template_id)
        if not template:
            return None

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

    def delete_template(self, template_id: int) -> bool:
        """
        删除模板

        Args:
            template_id: 模板 ID

        Returns:
            是否成功
        """
        template = self.template_repo.get_by_id(template_id)
        if not template:
            return False

        return self.template_repo.delete(template)

    def get_template_versions(self, template_id: int) -> List[TemplateVersionResponse]:
        """
        获取模板版本列表

        Args:
            template_id: 模板 ID

        Returns:
            版本响应列表
        """
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
        """
        # 获取指定版本
        target_version = self.version_repo.get_by_version(template_id, version)
        if not target_version:
            return None

        # 获取当前模板
        template = self.template_repo.get_by_id(template_id)
        if not template:
            return None

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
        """
        template = self.template_repo.get_by_id(template_id)
        if not template:
            return False

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
        from app.models.user import User

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

    def get_template_shares(self, template_id: int) -> List[dict]:
        """
        获取模板的分享用户列表

        Args:
            template_id: 模板 ID

        Returns:
            用户信息列表（包含用户ID、用户名、邮箱、分享时间）
        """
        from app.models.user import User

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

    def unshare_template(self, template_id: int, user_id: int) -> bool:
        """
        取消分享模板

        Args:
            template_id: 模板 ID
            user_id: 用户 ID

        Returns:
            是否成功
        """
        share = self.db.query(TemplateShare).filter(
            TemplateShare.template_id == template_id,
            TemplateShare.user_id == user_id
        ).first()

        if not share:
            return False

        self.db.delete(share)
        self.db.commit()
        return True

    def get_version_diff(self, template_id: int, version1: int, version2: int) -> dict:
        """
        获取两个版本之间的差异

        Args:
            template_id: 模板 ID
            version1: 版本号 1
            version2: 版本号 2

        Returns:
            版本差异
        """
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
