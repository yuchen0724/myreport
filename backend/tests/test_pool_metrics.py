"""连接池监控 API 测试 - 覆盖指标获取、Redis 缓存、边界条件"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.pool import QueuePool
from sqlalchemy import create_engine as sa_create_engine

from app.utils.connection_pool_manager import ConnectionPoolManager, CachableEngine
from app.services.pool_monitor_service import PoolMonitorService, PoolMetricsCache
from app.schemas.pool_metrics import PoolMetricsResponse, AllPoolMetricsResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置单例状态"""
    ConnectionPoolManager._instance = None
    ConnectionPoolManager._engines = {}
    yield


@pytest.fixture
def mock_redis():
    """创建 mock Redis 客户端"""
    client = MagicMock()
    client.get.return_value = None
    client.setex.return_value = True
    client.delete.return_value = 1
    client.keys.return_value = []
    return client


@pytest.fixture
def pool_cache(mock_redis):
    """创建带 mock Redis 的缓存实例"""
    cache = PoolMetricsCache.__new__(PoolMetricsCache)
    cache.redis_client = mock_redis
    return cache


@pytest.fixture(autouse=True)
def use_sqlite_engine():
    """将 create_engine 替换为 SQLite 内存数据库"""
    with patch("app.utils.connection_pool_manager.create_engine") as mock:
        def _make_sqlite(url, **kwargs):
            return sa_create_engine(
                "sqlite:///:memory:",
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                connect_args={"check_same_thread": False},
            )
        mock.side_effect = _make_sqlite
        yield


# ---------------------------------------------------------------------------
# PoolMonitorService 测试
# ---------------------------------------------------------------------------

class TestPoolMonitorService:
    """PoolMonitorService 单元测试"""

    def test_get_metrics_no_pool(self, db_session):
        """连接池未创建时应返回默认指标"""
        # 创建数据源
        from app.models.data_source import DataSource
        ds = DataSource(
            name="test_ds",
            type="MYSQL",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password_encrypted="encrypted",
        )
        db_session.add(ds)
        db_session.commit()
        db_session.refresh(ds)

        service = PoolMonitorService(db_session)
        metrics = service.get_metrics(ds.id)
        assert metrics is not None
        assert metrics.active_connections == 0
        assert metrics.is_active is False

    def test_get_metrics_nonexistent_ds(self, db_session):
        """不存在的数据源应返回 None"""
        service = PoolMonitorService(db_session)
        metrics = service.get_metrics(9999)
        assert metrics is None

    def test_get_metrics_with_pool(self, db_session):
        """连接池已创建时应返回实际指标"""
        from app.models.data_source import DataSource
        ds = DataSource(
            name="test_ds_pool",
            type="MYSQL",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password_encrypted="encrypted",
        )
        db_session.add(ds)
        db_session.commit()
        db_session.refresh(ds)

        # 创建连接池
        mgr = ConnectionPoolManager()
        engine_obj = mgr.get_engine(
            ds_id=ds.id,
            ds_type="MYSQL",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="password",
        )

        service = PoolMonitorService(db_session)
        metrics = service.get_metrics(ds.id)
        assert metrics is not None
        assert metrics.is_active is True
        assert metrics.pool_size == 5
        assert metrics.data_source_id == ds.id
        assert metrics.data_source_name == "test_ds_pool"

    def test_get_all_metrics(self, db_session):
        """获取所有数据源指标"""
        from app.models.data_source import DataSource
        ds1 = DataSource(
            name="ds1", type="MYSQL", host="h1", port=3306,
            database="d1", username="u", password_encrypted="p",
        )
        ds2 = DataSource(
            name="ds2", type="POSTGRESQL", host="h2", port=5432,
            database="d2", username="u", password_encrypted="p",
        )
        db_session.add_all([ds1, ds2])
        db_session.commit()
        db_session.refresh(ds1)
        db_session.refresh(ds2)

        # 为 ds1 创建连接池
        mgr = ConnectionPoolManager()
        mgr.get_engine(
            ds_id=ds1.id, ds_type="MYSQL", host="h1", port=3306,
            database="d1", username="u", password="p",
        )

        service = PoolMonitorService(db_session)
        result = service.get_all_metrics()
        assert isinstance(result, AllPoolMetricsResponse)
        assert len(result.pools) >= 2
        # ds1 应该是 active 的
        ds1_metrics = [p for p in result.pools if p.data_source_id == ds1.id]
        assert len(ds1_metrics) == 1
        assert ds1_metrics[0].is_active is True

    def test_record_query_time(self, db_session):
        """记录查询时间后应影响平均查询时间"""
        from app.models.data_source import DataSource
        ds = DataSource(
            name="ds_time", type="MYSQL", host="h", port=3306,
            database="d", username="u", password_encrypted="p",
        )
        db_session.add(ds)
        db_session.commit()
        db_session.refresh(ds)

        service = PoolMonitorService(db_session)
        service.record_query_time(ds.id, 100.0)
        service.record_query_time(ds.id, 200.0)

        avg = service._get_avg_query_time(ds.id)
        assert avg == 150.0

    def test_record_query_time_limits_history(self, db_session):
        """查询时间历史应限制为最近100条"""
        service = PoolMonitorService(db_session)
        ds_id = 999
        for i in range(150):
            service.record_query_time(ds_id, float(i))

        with service._query_lock:
            assert len(service._query_times[ds_id]) == 100


# ---------------------------------------------------------------------------
# PoolMetricsCache 测试
# ---------------------------------------------------------------------------

class TestPoolMetricsCache:
    """PoolMetricsCache 单元测试"""

    def test_get_returns_none_when_no_redis(self):
        """无 Redis 时应返回 None"""
        cache = PoolMetricsCache.__new__(PoolMetricsCache)
        cache.redis_client = None
        assert cache.get(1) is None

    def test_get_returns_none_when_empty(self, pool_cache):
        """Redis 无数据时应返回 None"""
        pool_cache.redis_client.get.return_value = None
        assert pool_cache.get(1) is None

    def test_set_and_get(self, pool_cache):
        """设置后获取应返回缓存数据"""
        import json
        metrics = {"data_source_id": 1, "active_connections": 3}
        pool_cache.set(1, metrics)
        pool_cache.redis_client.get.return_value = json.dumps(metrics)

        result = pool_cache.get(1)
        assert result is not None
        assert result["data_source_id"] == 1
        assert result["active_connections"] == 3

    def test_set_all_and_get_all(self, pool_cache):
        """设置和获取所有指标"""
        import json
        data = {"pools": [], "total_active": 0}
        pool_cache.set_all(data)
        pool_cache.redis_client.get.return_value = json.dumps(data)

        result = pool_cache.get_all()
        assert result is not None
        assert "pools" in result

    def test_invalidate(self, pool_cache):
        """清除缓存应调用 Redis delete"""
        pool_cache.invalidate(1)
        pool_cache.redis_client.delete.assert_called_with("pool_metrics:1")

    def test_invalidate_all(self, pool_cache):
        """清除所有缓存应删除匹配的 keys"""
        pool_cache.redis_client.keys.return_value = ["pool_metrics:1", "pool_metrics:2"]
        pool_cache.invalidate_all()
        pool_cache.redis_client.delete.assert_called_once_with("pool_metrics:1", "pool_metrics:2")

    def test_invalidate_all_no_keys(self, pool_cache):
        """无匹配 key 时不应调用 delete"""
        pool_cache.redis_client.keys.return_value = []
        pool_cache.invalidate_all()
        pool_cache.redis_client.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Schema 测试
# ---------------------------------------------------------------------------

class TestPoolMetricsSchema:
    """Schema 验证测试"""

    def test_pool_metrics_response_defaults(self):
        """默认值测试"""
        resp = PoolMetricsResponse(
            data_source_id=1,
            data_source_name="test",
            data_source_type="MYSQL",
        )
        assert resp.active_connections == 0
        assert resp.idle_connections == 0
        assert resp.waiting_queue_length == 0
        assert resp.avg_query_time_ms == 0.0
        assert resp.is_active is False

    def test_pool_metrics_response_to_dict(self):
        """序列化测试"""
        resp = PoolMetricsResponse(
            data_source_id=1,
            data_source_name="test",
            data_source_type="MYSQL",
            active_connections=5,
            idle_connections=3,
            is_active=True,
        )
        d = resp.model_dump()
        assert d["data_source_id"] == 1
        assert d["active_connections"] == 5
        assert d["is_active"] is True

    def test_all_pool_metrics_response(self):
        """AllPoolMetricsResponse 测试"""
        resp = AllPoolMetricsResponse(
            pools=[
                PoolMetricsResponse(
                    data_source_id=1, data_source_name="a", data_source_type="MYSQL",
                    active_connections=2, idle_connections=3,
                ),
                PoolMetricsResponse(
                    data_source_id=2, data_source_name="b", data_source_type="PG",
                    active_connections=1, idle_connections=1,
                ),
            ],
            total_active=3,
            total_idle=4,
        )
        assert len(resp.pools) == 2
        assert resp.total_active == 3
        assert resp.total_idle == 4


# ---------------------------------------------------------------------------
# API 集成测试
# ---------------------------------------------------------------------------

class TestPoolMetricsAPI:
    """连接池监控 API 端点测试"""

    def test_get_pool_metrics_unauthorized(self, client):
        """未认证请求应返回 401"""
        resp = client.get("/api/metrics/pool/1")
        assert resp.status_code == 401

    def test_get_pool_metrics_not_found(self, client, auth_headers):
        """不存在的数据源应返回 404"""
        resp = client.get("/api/metrics/pool/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_pool_metrics_success(self, client, auth_headers, db_session, test_user):
        """成功获取连接池指标"""
        from app.models.data_source import DataSource
        ds = DataSource(
            name="api_test_ds", type="MYSQL", host="localhost", port=3306,
            database="testdb", username="root", password_encrypted="encrypted",
            created_by=test_user.id,
        )
        db_session.add(ds)
        db_session.commit()
        db_session.refresh(ds)

        with patch("app.api.pool_metrics._metrics_cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True

            resp = client.get(f"/api/metrics/pool/{ds.id}", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["data_source_id"] == ds.id
            assert data["data_source_name"] == "api_test_ds"
            assert "active_connections" in data
            assert "is_active" in data

    def test_get_all_pool_metrics(self, client, admin_auth_headers, db_session):
        """获取所有连接池指标"""
        with patch("app.api.pool_metrics._metrics_cache") as mock_cache:
            mock_cache.get_all.return_value = None
            mock_cache.set_all.return_value = True

            resp = client.get("/api/metrics/pool", headers=admin_auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "pools" in data
            assert "total_active" in data
            assert "total_idle" in data
            assert "total_waiting" in data

    def test_get_pool_metrics_from_cache(self, client, auth_headers, db_session, test_user):
        """从缓存获取指标"""
        import json
        from app.models.data_source import DataSource

        ds = DataSource(
            name="cached_ds", type="MYSQL", host="localhost", port=3306,
            database="testdb", username="root", password_encrypted="encrypted",
            created_by=test_user.id,
        )
        db_session.add(ds)
        db_session.commit()
        db_session.refresh(ds)
        cached_data = {
            "data_source_id": ds.id,
            "data_source_name": "cached_ds",
            "data_source_type": "MYSQL",
            "active_connections": 2,
            "idle_connections": 3,
            "waiting_queue_length": 0,
            "avg_query_time_ms": 45.5,
            "pool_size": 5,
            "max_overflow": 10,
            "total_connections": 5,
            "checked_out": 2,
            "checked_in": 3,
            "overflow": 0,
            "is_active": True,
        }

        with patch("app.api.pool_metrics._metrics_cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            resp = client.get(f"/api/metrics/pool/{ds.id}", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["data_source_name"] == "cached_ds"
            assert data["active_connections"] == 2
