"""
菜单服务层
"""
import json
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from app.repositories.menu_repository import MenuRepository
from app.repositories.template_repository import TemplateRepository
from app.schemas.menu import MenuCreate, MenuUpdate, MenuResponse, MenuTreeResponse
from app.models.menu import Menu


class MenuService:
    """菜单服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = MenuRepository(db)
    
    def get_by_id(self, menu_id: int) -> Optional[MenuResponse]:
        """根据ID获取菜单"""
        menu = self.repo.get_by_id(menu_id)
        if not menu:
            return None
        return MenuResponse.model_validate(menu)
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[MenuResponse]:
        """获取所有菜单"""
        menus = self.repo.get_all(skip, limit)
        return [MenuResponse.model_validate(m) for m in menus]
    
    def get_enabled_menus(self) -> List[MenuResponse]:
        """获取所有启用的菜��"""
        menus = self.repo.get_enabled_menus()
        return [MenuResponse.model_validate(m) for m in menus]
    
    def get_tree(self) -> List[Dict]:
        """获取菜单树（含模板名称）"""
        all_menus = self.repo.get_enabled_menus()

        # 批量加载模板名称（避免 N+1 查询）
        template_ids = [m.template_id for m in all_menus if m.template_id]
        template_names = {}
        if template_ids:
            template_repo = TemplateRepository(self.db)
            templates = template_repo.get_by_ids(template_ids)
            template_names = {t.id: t.name for t in templates}

        # 构建所有菜单的字典（含模板名称）
        menu_dict = {}
        for menu in all_menus:
            template_name = template_names.get(menu.template_id) if menu.template_id else None
            menu_dict[menu.id] = {
                "id": menu.id,
                "name": menu.name,
                "path": menu.path,
                "icon": menu.icon,
                "sort_order": menu.sort_order,
                "parent_id": menu.parent_id,
                "template_id": menu.template_id,
                "template_name": template_name,
                "is_enabled": menu.is_enabled,
                "is_visible": menu.is_visible,
                "remark": menu.remark,
                "children": []
            }
        
        # 组装树形结构
        tree = []
        for menu in all_menus:
            if menu.parent_id:
                parent = menu_dict.get(menu.parent_id)
                if parent:
                    parent["children"].append(menu_dict[menu.id])
            else:
                tree.append(menu_dict[menu.id])
        
        return tree
    
    def create(self, data: MenuCreate) -> MenuResponse:
        """创建菜单"""
        menu = self.repo.create(data.model_dump())
        return MenuResponse.model_validate(menu)
    
    def update(self, menu_id: int, data: MenuUpdate) -> Optional[MenuResponse]:
        """更新菜单"""
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        menu = self.repo.update(menu_id, update_data)
        if not menu:
            return None
        return MenuResponse.model_validate(menu)
    
    def delete(self, menu_id: int) -> bool:
        """删除菜单"""
        return self.repo.delete(menu_id)
    
    def get_count(self) -> int:
        """获取菜单总数"""
        return self.repo.get_count()
    
    def get_menu_with_template(self, menu_id: int) -> Optional[Dict]:
        """获取菜单及其关联的报表模板"""
        menu = self.repo.get_by_id(menu_id)
        if not menu:
            return None

        result = {
            "id": menu.id,
            "name": menu.name,
            "path": menu.path,
            "icon": menu.icon,
            "template_id": menu.template_id,
            "is_enabled": menu.is_enabled,
        }

        if menu.template_id:
            # 通过 TemplateRepository 查询关联模板（避免 template relationship 依赖）
            from app.repositories.template_repository import TemplateRepository
            template_repo = TemplateRepository(self.db)
            tmpl = template_repo.get_by_id(menu.template_id)
            if tmpl:
                result["template"] = {
                    "id": tmpl.id,
                    "name": tmpl.name,
                    "description": tmpl.description,
                    "config": json.loads(tmpl.config) if isinstance(tmpl.config, str) else tmpl.config,
                }

        return result