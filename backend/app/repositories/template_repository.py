# backend/app/repositories/template_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.template import Template

class TemplateRepository:
    """模板数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, template: Template) -> Template:
        """创建模板"""
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_by_id(self, template_id: int) -> Optional[Template]:
        """根据 ID 获取模板"""
        return self.db.query(Template).filter(Template.id == template_id).first()

    def get_all(self, user_id: Optional[int] = None) -> List[Template]:
        """获取所有模板"""
        query = self.db.query(Template)
        if user_id:
            query = query.filter(Template.created_by == user_id)
        return query.all()

    def update(self, template: Template) -> Template:
        """更新模板"""
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template: Template) -> bool:
        """删除模板"""
        self.db.delete(template)
        self.db.commit()
        return True
