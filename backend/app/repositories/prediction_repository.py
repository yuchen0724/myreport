from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.models.prediction import PredictionResult, PredictionModel


class PredictionModelRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> PredictionModel:
        model = PredictionModel(**kwargs)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get_latest_ready(self, data_source_id: int) -> Optional[PredictionModel]:
        return (
            self.db.query(PredictionModel)
            .filter(
                PredictionModel.data_source_id == data_source_id,
                PredictionModel.status == "ready",
            )
            .order_by(PredictionModel.id.desc())
            .first()
        )

    def update_status(self, model_id: int, status: str, **extra) -> None:
        self.db.query(PredictionModel).filter(PredictionModel.id == model_id).update(
            {"status": status, **extra}
        )
        self.db.commit()

    def get_by_id(self, model_id: int) -> Optional[PredictionModel]:
        return self.db.query(PredictionModel).filter(PredictionModel.id == model_id).first()

    def get_all(self, data_source_id: Optional[int] = None,
                skip: int = 0, limit: int = 100) -> List[PredictionModel]:
        q = self.db.query(PredictionModel)
        if data_source_id:
            q = q.filter(PredictionModel.data_source_id == data_source_id)
        return q.order_by(PredictionModel.id.desc()).offset(skip).limit(limit).all()


class PredictionResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_save(self, results: List[PredictionResult]) -> int:
        self.db.bulk_save_objects(results)
        self.db.commit()
        return len(results)

    def get_forecast(
        self, data_source_id: int, store_code: Optional[str] = None,
        start_date: Optional[date] = None, end_date: Optional[date] = None,
        limit: int = 100, offset: int = 0
    ) -> List[PredictionResult]:
        q = self.db.query(PredictionResult).filter(
            PredictionResult.data_source_id == data_source_id
        )
        if store_code:
            q = q.filter(PredictionResult.store_code == store_code)
        if start_date:
            q = q.filter(PredictionResult.forecast_date >= start_date)
        if end_date:
            q = q.filter(PredictionResult.forecast_date <= end_date)
        return q.order_by(PredictionResult.forecast_date).offset(offset).limit(limit).all()
