from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.models.prediction import PredictionResult, PredictionModel, ForecastHistory


class ForecastHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> ForecastHistory:
        record = ForecastHistory(**kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_user(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[ForecastHistory]:
        q = self.db.query(ForecastHistory)
        if user_id is not None:
            q = q.filter(ForecastHistory.created_by == user_id)
        return q.order_by(ForecastHistory.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_task_id(self, task_id: str) -> List[ForecastHistory]:
        return self.db.query(ForecastHistory).filter(
            ForecastHistory.task_id == task_id
        ).all()


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

    def get_running_by_user(self, user_id: int) -> List[PredictionModel]:
        """获取用户正在进行的训练任务

        注意：这里只查询数据库中的模型记录。
        真正的"运行中"状态判定在 API 层通过 Redis 确认。
        """
        return (
            self.db.query(PredictionModel)
            .filter(
                PredictionModel.created_by == user_id,
                PredictionModel.deleted_at.is_(None),
            )
            .order_by(PredictionModel.id.desc())
            .all()
        )


class PredictionResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_save(self, results: List[PredictionResult]) -> int:
        self.db.bulk_save_objects(results)
        self.db.commit()
        return len(results)

    ALLOWED_SORT_FIELDS = {
        "forecast_date": PredictionResult.forecast_date,
        "predicted_value": PredictionResult.predicted_value,
        "store_code": PredictionResult.store_code,
        "matnr": PredictionResult.matnr,
    }

    def get_forecast(
        self, data_source_id: int, model_id: Optional[int] = None,
        store_code: Optional[str] = None, matnr: Optional[str] = None,
        start_date: Optional[date] = None, end_date: Optional[date] = None,
        sort_by: str = "forecast_date", sort_order: str = "asc",
        limit: int = 100, offset: int = 0
    ) -> List[PredictionResult]:
        q = self.db.query(PredictionResult).filter(
            PredictionResult.data_source_id == data_source_id
        )
        if model_id:
            q = q.filter(PredictionResult.model_id == model_id)
        if store_code:
            q = q.filter(PredictionResult.store_code == store_code)
        if matnr:
            q = q.filter(PredictionResult.matnr == matnr)
        if start_date:
            q = q.filter(PredictionResult.forecast_date >= start_date)
        if end_date:
            q = q.filter(PredictionResult.forecast_date <= end_date)

        sort_col = self.ALLOWED_SORT_FIELDS.get(sort_by, PredictionResult.forecast_date)
        order_fn = sort_col.desc if sort_order == "desc" else sort_col.asc
        return q.order_by(order_fn()).offset(offset).limit(limit).all()

    def count_forecast(
        self, data_source_id: int, model_id: Optional[int] = None,
        store_code: Optional[str] = None, matnr: Optional[str] = None,
        start_date: Optional[date] = None, end_date: Optional[date] = None,
    ) -> int:
        q = self.db.query(PredictionResult).filter(
            PredictionResult.data_source_id == data_source_id
        )
        if model_id:
            q = q.filter(PredictionResult.model_id == model_id)
        if store_code:
            q = q.filter(PredictionResult.store_code == store_code)
        if matnr:
            q = q.filter(PredictionResult.matnr == matnr)
        if start_date:
            q = q.filter(PredictionResult.forecast_date >= start_date)
        if end_date:
            q = q.filter(PredictionResult.forecast_date <= end_date)
        return q.count()
