# backend/app/services/favorite_service.py
from sqlalchemy.orm import Session
from app.models.favorite import Favorite
from app.models.template import Template
from app.schemas.favorite import FavoriteCreate, FavoriteUpdate

class FavoriteService:
    def __init__(self, db: Session):
        self.db = db

    def get_favorites(self, user_id: int, category: str = None):
        query = self.db.query(Favorite, Template.name, Template.description).join(
            Template, Favorite.template_id == Template.id
        ).filter(Favorite.user_id == user_id)
        if category:
            query = query.filter(Favorite.category == category)
        
        results = []
        for fav, template_name, template_desc in query.order_by(Favorite.created_at.desc()).all():
            fav_dict = {
                "id": fav.id,
                "user_id": fav.user_id,
                "template_id": fav.template_id,
                "category": fav.category,
                "note": fav.note,
                "created_at": fav.created_at,
                "template_name": template_name,
                "template_description": template_desc
            }
            results.append(fav_dict)
        return results

    def get_favorite(self, favorite_id: int, user_id: int):
        return self.db.query(Favorite).filter(
            Favorite.id == favorite_id,
            Favorite.user_id == user_id
        ).first()

    def add_favorite(self, data: FavoriteCreate, user_id: int):
        # 检查是否已收藏
        existing = self.db.query(Favorite).filter(
            Favorite.user_id == user_id,
            Favorite.template_id == data.template_id
        ).first()
        
        if existing:
            return existing  # 或者抛出异常/更新分类
        
        favorite = Favorite(
            user_id=user_id,
            template_id=data.template_id,
            category=data.category,
            note=data.note
        )
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def update_favorite(self, favorite_id: int, data: FavoriteUpdate, user_id: int):
        favorite = self.get_favorite(favorite_id, user_id)
        if not favorite:
            return None
        
        if data.category is not None:
            favorite.category = data.category
        if data.note is not None:
            favorite.note = data.note
            
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def remove_favorite(self, favorite_id: int, user_id: int):
        favorite = self.get_favorite(favorite_id, user_id)
        if favorite:
            self.db.delete(favorite)
            self.db.commit()
            return True
        return False

    def remove_favorite_by_template(self, template_id: int, user_id: int):
        favorite = self.db.query(Favorite).filter(
            Favorite.template_id == template_id,
            Favorite.user_id == user_id
        ).first()
        if favorite:
            self.db.delete(favorite)
            self.db.commit()
            return True
        return False

    def is_favorited(self, template_id: int, user_id: int):
        return self.db.query(Favorite).filter(
            Favorite.template_id == template_id,
            Favorite.user_id == user_id
        ).first() is not None
