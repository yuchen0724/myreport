"""
菜单 Repository
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.menu import Menu


class MenuRepository:
    """菜单数据访问层"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, menu_id: int) -> Optional[Menu]:
        """根据ID获取菜单"""
        return self.db.query(Menu).filter(Menu.id == menu_id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Menu]:
        """获取所有菜单"""
        return self.db.query(Menu).order_by(Menu.sort_order, Menu.id).offset(skip).limit(limit).all()
    
    def get_enabled_menus(self) -> List[Menu]:
        """获取所有启用的菜单"""
        return self.db.query(Menu).filter(Menu.is_enabled == True).order_by(Menu.sort_order, Menu.id).all()
    
    def get_root_menus(self) -> List[Menu]:
        """获取根菜单（无父级）"""
        return self.db.query(Menu).filter(
            Menu.parent_id == None,
            Menu.is_visible == True,
            Menu.is_enabled == True
        ).order_by(Menu.sort_order, Menu.id).all()
    
    def get_by_parent_id(self, parent_id: int) -> List[Menu]:
        """根据父ID获取子菜单"""
        return self.db.query(Menu).filter(
            Menu.parent_id == parent_id,
            Menu.is_visible == True,
            Menu.is_enabled == True
        ).order_by(Menu.sort_order, Menu.id).all()
    
    def get_tree(self) -> List[Menu]:
        """获取菜单树"""
        # 这里只获取一级，后续在 service 层组装树形结构
        return self.get_root_menus()
    
    def create(self, data: dict) -> Menu:
        """创建菜单"""
        menu = Menu(**data)
        self.db.add(menu)
        self.db.flush()
        self.db.refresh(menu)
        return menu
    
    def update(self, menu_id: int, data: dict) -> Optional[Menu]:
        """更新菜单"""
        menu = self.get_by_id(menu_id)
        if not menu:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(menu, key, value)
        self.db.flush()
        self.db.refresh(menu)
        return menu
    
    def delete(self, menu_id: int) -> bool:
        """删除菜单"""
        menu = self.get_by_id(menu_id)
        if not menu:
            return False
        # 删除子菜单
        self.db.query(Menu).filter(Menu.parent_id == menu_id).delete()
        self.db.delete(menu)
        self.db.flush()
        return True
    
    def get_count(self) -> int:
        """获取菜单总数"""
        return self.db.query(func.count(Menu.id)).scalar()
    
    def get_children_count(self, parent_id: int) -> int:
        """获取子菜单数量"""
        return self.db.query(func.count(Menu.id)).filter(Menu.parent_id == parent_id).scalar()