from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.data_source import DataSource
from app.core.security import get_password_hash


class DataSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, ds_id: int) -> Optional[DataSource]:
        return self.db.query(DataSource).filter(DataSource.id == ds_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[DataSource]:
        return self.db.query(DataSource).offset(skip).limit(limit).all()

    def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[DataSource]:
        return self.db.query(DataSource).filter(DataSource.created_by == user_id).offset(skip).limit(limit).all()

    def create(self, ds_data: dict, user_id: int) -> DataSource:
        db_ds = DataSource(
            name=ds_data["name"],
            type=ds_data["type"],
            host=ds_data["host"],
            port=ds_data["port"],
            database=ds_data["database"],
            username=ds_data["username"],
            password_encrypted=ds_data["password"],  # TODO: 加密存储
            is_active=ds_data.get("is_active", True),
            created_by=user_id,
        )
        self.db.add(db_ds)
        self.db.commit()
        self.db.refresh(db_ds)
        return db_ds

    def update(self, ds: DataSource, ds_data: dict) -> DataSource:
        for key, value in ds_data.items():
            if hasattr(ds, key) and value is not None:
                setattr(ds, key, value)
        self.db.commit()
        self.db.refresh(ds)
        return ds

    def delete(self, ds: DataSource) -> bool:
        self.db.delete(ds)
        self.db.commit()
        return True
