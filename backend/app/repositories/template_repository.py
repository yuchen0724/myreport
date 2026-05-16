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

    def get_by_ids(self, ids: List[int]) -> List[Template]:
        """批量获取模板"""
        return self.db.query(Template).filter(Template.id.in_(ids)).all()

    def get_all(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[Template]:
        """获取所有模板（支持分页）"""
        query = self.db.query(Template)
        if user_id:
            # 如果指定了用户ID，只返回该用户创建的模板
            query = query.filter(Template.created_by == user_id)
        # 支持分页参数
        return query.offset(skip).limit(limit).all()

    def update(self, template: Template) -> Template:
        """更新模板"""
        self.db.flush()  # 先确保修改写入数据库
        self.db.commit()  # 提交事务
        self.db.refresh(template)
        return template

    def count(self, user_id: Optional[int] = None) -> int:
        """获取模板总数"""
        query = self.db.query(Template)
        if user_id:
            query = query.filter(Template.created_by == user_id)
        return query.count()

    def delete(self, template: Template) -> bool:
        """删除模板"""
        self.db.delete(template)
        self.db.commit()
        return True
