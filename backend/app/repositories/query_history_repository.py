from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.query_history import QueryHistory


class QueryHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, history_data: dict) -> QueryHistory:
        db_history = QueryHistory(**history_data)
        self.db.add(db_history)
        self.db.flush()
        self.db.refresh(db_history)
        return db_history

    def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[QueryHistory]:
        return self.db.query(QueryHistory).filter(
            QueryHistory.user_id == user_id
        ).order_by(QueryHistory.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, history_id: int) -> Optional[QueryHistory]:
        return self.db.query(QueryHistory).filter(QueryHistory.id == history_id).first()
