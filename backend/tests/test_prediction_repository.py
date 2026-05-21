"""测试 prediction_repository.py - PredictionModelRepository / PredictionResultRepository / ForecastHistoryRepository

使用 SQLite 内存数据库 + 真实模型表 (from app.models.prediction import ...)。
按 conftest.py 的测试模式编写。
"""
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.models.prediction import PredictionModel, PredictionResult, ForecastHistory
from app.repositories.prediction_repository import (
    PredictionModelRepository,
    PredictionResultRepository,
    ForecastHistoryRepository,
)


# =============================================================
# PredictionModelRepository 测试
# =============================================================


class TestPredictionModelRepository:
    """PredictionModelRepository 单元测试"""

    def test_create(self, db_session: Session):
        """create: 创建模型记录，返回包含自增 id 的对象"""
        repo = PredictionModelRepository(db_session)
        model = repo.create(
            data_source_id=1,
            model_type="lightgbm",
            status="training",
            created_by=42,
        )
        assert model.id is not None and model.id > 0
        assert model.data_source_id == 1
        assert model.model_type == "lightgbm"
        assert model.status == "training"
        assert model.created_by == 42
        assert model.created_at is not None

    def test_get_latest_ready(self, db_session: Session):
        """get_latest_ready: 按 data_source_id 过滤并返回最新的 ready 模型"""
        repo = PredictionModelRepository(db_session)
        # 创建多个模型：different status, different order
        m1 = repo.create(data_source_id=1, status="training")
        m2 = repo.create(data_source_id=1, status="ready")
        m3 = repo.create(data_source_id=1, status="ready")
        m4 = repo.create(data_source_id=2, status="ready")

        latest = repo.get_latest_ready(data_source_id=1)
        assert latest is not None
        assert latest.id == m3.id  # 最新的 ready 记录
        assert latest.status == "ready"

        # data_source_id=2 也应返回
        latest2 = repo.get_latest_ready(data_source_id=2)
        assert latest2 is not None
        assert latest2.id == m4.id

        # 不存在对应的记录
        assert repo.get_latest_ready(data_source_id=999) is None

    def test_update_status(self, db_session: Session):
        """update_status: 更新模型状态及额外字段"""
        repo = PredictionModelRepository(db_session)
        model = repo.create(data_source_id=1, status="training")

        repo.update_status(model.id, status="ready", error_message=None)
        db_session.refresh(model)
        assert model.status == "ready"

        # 带额外字段
        now = datetime.now()
        repo.update_status(model.id, status="failed", error_message="oops", trained_at=now)
        db_session.refresh(model)
        assert model.status == "failed"
        assert model.error_message == "oops"
        assert model.trained_at == now

    def test_get_by_id(self, db_session: Session):
        """get_by_id: 根据 id 查询模型记录"""
        repo = PredictionModelRepository(db_session)
        model = repo.create(data_source_id=1, status="ready")

        found = repo.get_by_id(model.id)
        assert found is not None
        assert found.id == model.id

        assert repo.get_by_id(9999) is None

    def test_get_all(self, db_session: Session):
        """get_all: 分页查询，可按 data_source_id 过滤"""
        repo = PredictionModelRepository(db_session)
        for i in range(5):
            repo.create(data_source_id=1, status="ready")
        for i in range(3):
            repo.create(data_source_id=2, status="ready")

        all_records = repo.get_all()
        assert len(all_records) == 8

        # 按 data_source_id 过滤
        ds1 = repo.get_all(data_source_id=1)
        assert len(ds1) == 5
        for m in ds1:
            assert m.data_source_id == 1

        # 分页
        page1 = repo.get_all(data_source_id=1, skip=0, limit=2)
        assert len(page1) == 2

        page2 = repo.get_all(data_source_id=1, skip=2, limit=2)
        assert len(page2) == 2
        # 确保 page2 的 id 小于 page1（按 id desc 排序）
        assert page2[0].id < page1[-1].id

    def test_get_running_by_user(self, db_session: Session):
        """get_running_by_user: 返回未软删除的用户模型，按 id desc 排序"""
        repo = PredictionModelRepository(db_session)
        # 用户 1 创建 3 条
        m1 = repo.create(data_source_id=1, created_by=1, status="ready")
        m2 = repo.create(data_source_id=1, created_by=1, status="training")
        # 用户 2 创建 1 条
        m3 = repo.create(data_source_id=2, created_by=2, status="training")

        # 用户 1 的未软删除模型
        user1 = repo.get_running_by_user(user_id=1)
        assert len(user1) == 2
        assert user1[0].id == m2.id  # 最新在前

        # 用户 2
        user2 = repo.get_running_by_user(user_id=2)
        assert len(user2) == 1
        assert user2[0].id == m3.id

        # 软删除后不应返回
        from datetime import datetime, timezone, timedelta
        m2.deleted_at = datetime.now(timezone(timedelta(hours=8)))
        db_session.commit()
        user1_after = repo.get_running_by_user(user_id=1)
        assert len(user1_after) == 1
        assert user1_after[0].id == m1.id


# =============================================================
# PredictionResultRepository 测试
# =============================================================


class TestPredictionResultRepository:
    """PredictionResultRepository 单元测试"""

    @pytest.fixture(autouse=True)
    def _setup_results(self, db_session: Session):
        """为每个测试准备一批预测结果数据"""
        self.repo = PredictionResultRepository(db_session)
        self.ds_id = 10
        self.model_id = 100

        results = []
        for i, (store, matnr) in enumerate([("S001", "M001"), ("S002", "M002"), ("S003", "M003")]):
            for day_offset in range(5):
                results.append(
                    PredictionResult(
                        model_id=self.model_id,
                        data_source_id=self.ds_id,
                        store_code=store,
                        matnr=matnr,
                        ware_name=f"商品{matnr}",
                        forecast_date=date(2026, 6, 1) + timedelta(days=day_offset),
                        predicted_value=100.0 + i * 10 + day_offset,
                        lower_bound=90.0 + i * 10 + day_offset,
                        upper_bound=110.0 + i * 10 + day_offset,
                    )
                )
        self.all_results = results
        self.repo.bulk_save(results)

    def test_bulk_save(self, db_session: Session):
        """bulk_save: 批量保存返回插入条数"""
        count = self.repo.bulk_save([])
        assert count == 0

        new_results = [
            PredictionResult(
                model_id=self.model_id, data_source_id=self.ds_id,
                store_code="S004", matnr="M004",
                forecast_date=date(2026, 7, 1), predicted_value=200.0,
            )
        ]
        count = self.repo.bulk_save(new_results)
        assert count == 1

        # 验证确实写入了
        all_in_db = db_session.query(PredictionResult).count()
        assert all_in_db == 15 + 1  # 15 from fixture + 1 new

    def test_get_forecast_basic(self, db_session: Session):
        """get_forecast: 默认按 forecast_date 升序返回"""
        result = self.repo.get_forecast(data_source_id=self.ds_id)
        assert len(result) == 15
        # 默认升序
        dates = [r.forecast_date for r in result]
        assert dates == sorted(dates)

    def test_get_forecast_filter_by_model(self, db_session: Session):
        """get_forecast: 按 model_id 过滤"""
        result = self.repo.get_forecast(data_source_id=self.ds_id, model_id=self.model_id)
        assert len(result) == 15

        result2 = self.repo.get_forecast(data_source_id=self.ds_id, model_id=999)
        assert len(result2) == 0

    def test_get_forecast_filter_store_matnr(self, db_session: Session):
        """get_forecast: 按 store_code / matnr 过滤"""
        r = self.repo.get_forecast(data_source_id=self.ds_id, store_code="S001")
        assert len(r) == 5
        assert all(x.store_code == "S001" for x in r)

        r2 = self.repo.get_forecast(data_source_id=self.ds_id, matnr="M002")
        assert len(r2) == 5
        assert all(x.matnr == "M002" for x in r2)

        r3 = self.repo.get_forecast(data_source_id=self.ds_id, store_code="S001", matnr="M001")
        assert len(r3) == 5

    def test_get_forecast_filter_date_range(self, db_session: Session):
        """get_forecast: 按日期范围过滤"""
        r = self.repo.get_forecast(
            data_source_id=self.ds_id,
            start_date=date(2026, 6, 3),
            end_date=date(2026, 6, 5),
        )
        # 3 stores, 3 dates (6/3, 6/4, 6/5) = 9
        assert len(r) == 9

    def test_get_forecast_sort_order(self, db_session: Session):
        """get_forecast: 支持升降序排列"""
        asc = self.repo.get_forecast(
            data_source_id=self.ds_id, sort_by="predicted_value", sort_order="asc"
        )
        vals_asc = [r.predicted_value for r in asc]
        assert vals_asc == sorted(vals_asc)

        desc = self.repo.get_forecast(
            data_source_id=self.ds_id, sort_by="predicted_value", sort_order="desc"
        )
        vals_desc = [r.predicted_value for r in desc]
        assert vals_desc == sorted(vals_desc, reverse=True)

    def test_get_forecast_pagination(self, db_session: Session):
        """get_forecast: 分页"""
        page1 = self.repo.get_forecast(data_source_id=self.ds_id, limit=5, offset=0)
        assert len(page1) == 5

        page2 = self.repo.get_forecast(data_source_id=self.ds_id, limit=5, offset=5)
        assert len(page2) == 5
        # page2 ids should be greater than page1 ids (asc order)
        assert page2[0].id > page1[-1].id

    def test_get_forecast_sort_by_store_code(self, db_session: Session):
        """get_forecast: 按 store_code 排序"""
        r = self.repo.get_forecast(
            data_source_id=self.ds_id, sort_by="store_code", sort_order="asc"
        )
        codes = [x.store_code for x in r]
        assert codes == sorted(codes)

    def test_get_forecast_sort_by_matnr(self, db_session: Session):
        """get_forecast: 按 matnr 排序"""
        r = self.repo.get_forecast(
            data_source_id=self.ds_id, sort_by="matnr", sort_order="desc"
        )
        matnrs = [x.matnr for x in r]
        assert matnrs == sorted(matnrs, reverse=True)

    def test_count_forecast(self, db_session: Session):
        """count_forecast: 返回符合条件的结果总数"""
        total = self.repo.count_forecast(data_source_id=self.ds_id)
        assert total == 15

        filtered = self.repo.count_forecast(
            data_source_id=self.ds_id, store_code="S001"
        )
        assert filtered == 5

        filtered2 = self.repo.count_forecast(
            data_source_id=self.ds_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 2),
        )
        assert filtered2 == 6  # 3 stores * 2 dates

        # 不存在的
        none_count = self.repo.count_forecast(
            data_source_id=self.ds_id, model_id=999
        )
        assert none_count == 0


# =============================================================
# ForecastHistoryRepository 测试
# =============================================================


class TestForecastHistoryRepository:
    """ForecastHistoryRepository 单元测试"""

    def test_create(self, db_session: Session):
        """create: 创建预测历史记录"""
        repo = ForecastHistoryRepository(db_session)
        record = repo.create(
            task_id="task-001",
            data_source_id=1,
            forecast_days=7,
            status="running",
            created_by=42,
        )
        assert record.id is not None and record.id > 0
        assert record.task_id == "task-001"
        assert record.status == "running"
        assert record.created_by == 42

    def test_get_by_user(self, db_session: Session):
        """get_by_user: 按用户查询历史记录，分页倒序"""
        repo = ForecastHistoryRepository(db_session)
        r1 = repo.create(task_id="t1", data_source_id=1, forecast_days=7, created_by=1)
        r2 = repo.create(task_id="t2", data_source_id=1, forecast_days=7, created_by=1)
        r3 = repo.create(task_id="t3", data_source_id=1, forecast_days=7, created_by=2)

        user1 = repo.get_by_user(user_id=1)
        assert len(user1) == 2
        assert user1[0].id == r2.id  # 最新在前

        user2 = repo.get_by_user(user_id=2)
        assert len(user2) == 1
        assert user2[0].id == r3.id

        # 分页
        limited = repo.get_by_user(user_id=1, skip=0, limit=1)
        assert len(limited) == 1

        # 不传 user_id 返回全部
        all_records = repo.get_by_user()
        assert len(all_records) == 3

    def test_get_by_task_id(self, db_session: Session):
        """get_by_task_id: 按 task_id 查询历史记录"""
        repo = ForecastHistoryRepository(db_session)
        repo.create(task_id="task-common", data_source_id=1, forecast_days=7, created_by=1)
        repo.create(task_id="task-common", data_source_id=2, forecast_days=14, created_by=2)
        repo.create(task_id="task-other", data_source_id=1, forecast_days=30, created_by=1)

        records = repo.get_by_task_id("task-common")
        assert len(records) == 2
        assert all(r.task_id == "task-common" for r in records)

        records2 = repo.get_by_task_id("non-existent")
        assert len(records2) == 0
