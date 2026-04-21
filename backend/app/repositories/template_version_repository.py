# backend/app/repositories/template_version_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.template_version import TemplateVersion

class TemplateVersionRepository:
    """模板版本数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, version: TemplateVersion) -> TemplateVersion:
        """创建版本"""
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_by_template_id(self, template_id: int) -> List[TemplateVersion]:
        """获取模板的所有版本"""
        return self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id
        ).order_by(TemplateVersion.version.desc()).all()

    def get_by_version(self, template_id: int, version: int) -> Optional[TemplateVersion]:
        """获取指定版本"""
        return self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == version
        ).first()
