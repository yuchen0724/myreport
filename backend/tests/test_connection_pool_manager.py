"""ConnectionPoolManager 测试 - 覆盖单例模式、get_engine（缓存命中/失效重建）、dispose_engine、dispose_all

使用 SQLite 代替真实数据库，按 conftest.py 的测试模式编写。
"""

import time
import threading
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.pool import QueuePool

from app.utils.connection_pool_manager import ConnectionPoolManager, CachableEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置单例状态，避免测试间相互干扰"""
    ConnectionPoolManager._instance = None
    ConnectionPoolManager._engines = {}
    yield


@pytest.fixture(autouse=True)
def use_sqlite_engine():
    """将 create_engine 替换为 SQLite 内存数据库（使用 QueuePool 以支持 pool.checkedin()）"""
    with patch("app.utils.connection_pool_manager.create_engine") as mock:

        def _make_sqlite(url, **kwargs):
            # 忽略调用方传入的 pool 参数，使用 SQLite + QueuePool
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
# Tests
# ---------------------------------------------------------------------------


class TestSingleton:
    """单例模式测试"""

    def test_singleton_same_instance(self):
        """多个实例应指向同一个对象"""
        mgr1 = ConnectionPoolManager()
        mgr2 = ConnectionPoolManager()
        assert mgr1 is mgr2

    def test_singleton_class_level(self):
        """类变量 _instance 应被正确设置"""
        mgr = ConnectionPoolManager()
        assert ConnectionPoolManager._instance is mgr

    def test_global_pool_manager_is_instance(self):
        """模块级全局实例 pool_manager 是 ConnectionPoolManager 实例"""
        from app.utils.connection_pool_manager import pool_manager

        assert isinstance(pool_manager, ConnectionPoolManager)

    def test_concurrent_singleton_safety(self):
        """并发获取实例应保证单例"""
        instances = []

        def _create():
            instances.append(ConnectionPoolManager())

        threads = [threading.Thread(target=_create) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(i is instances[0] for i in instances)


class TestGetEngine:
    """get_engine 方法测试"""

    COMMON_KWARGS = dict(
        ds_id=1,
        ds_type="MYSQL",
        host="localhost",
        port=3306,
        database="testdb",
        username="root",
        password="password",
    )

    def test_creates_new_engine(self):
        """创建新连接池应返回 CachableEngine 并缓存"""
        mgr = ConnectionPoolManager()
        engine_obj = mgr.get_engine(**self.COMMON_KWARGS)
        assert isinstance(engine_obj, CachableEngine)
        assert engine_obj.engine is not None
        assert 1 in ConnectionPoolManager._engines

    def test_cache_hit(self):
        """相同 ds_id 应命中缓存，返回同一对象"""
        mgr = ConnectionPoolManager()
        e1 = mgr.get_engine(**self.COMMON_KWARGS)
        e2 = mgr.get_engine(**self.COMMON_KWARGS)
        assert e1 is e2

    def test_cache_different_ds_id(self):
        """不同 ds_id 应创建不同的 engine"""
        mgr = ConnectionPoolManager()
        e1 = mgr.get_engine(**self.COMMON_KWARGS)
        e2 = mgr.get_engine(
            ds_id=2,
            ds_type="POSTGRESQL",
            host="localhost",
            port=5432,
            database="testdb2",
            username="user",
            password="pass",
        )
        assert e1 is not e2
        assert len(ConnectionPoolManager._engines) == 2

    def test_cache_rebuild_on_invalid(self):
        """连接池失效（checkedin < 0）应触发重建"""
        mgr = ConnectionPoolManager()
        e1 = mgr.get_engine(**self.COMMON_KWARGS)

        # 模拟连接池失效 —— 让 pool.checkedin() 返回 -1
        e1.engine.pool.checkedin = MagicMock(return_value=-1)

        e2 = mgr.get_engine(**self.COMMON_KWARGS)
        assert e1 is not e2

    def test_last_access_updated_on_cache_hit(self):
        """缓存命中时应更新 last_access"""
        mgr = ConnectionPoolManager()
        e1 = mgr.get_engine(**self.COMMON_KWARGS)
        old_access = e1.last_access

        # 短暂等待后再次获取
        time.sleep(0.01)
        e2 = mgr.get_engine(**self.COMMON_KWARGS)
        assert e2.last_access > old_access

    def test_unsupported_ds_type_raises(self):
        """不支持的数据源类型应抛出 ValueError"""
        mgr = ConnectionPoolManager()
        with pytest.raises(ValueError, match="不支持的数据源类型"):
            mgr.get_engine(
                ds_id=99,
                ds_type="ORACLE",
                host="localhost",
                port=1521,
                database="xepdb1",
                username="system",
                password="oracle",
            )

    def test_postgresql_creates_successfully(self):
        """POSTGRESQL 类型应正常创建"""
        mgr = ConnectionPoolManager()
        eng = mgr.get_engine(
            ds_id=10,
            ds_type="POSTGRESQL",
            host="pg.example.com",
            port=5432,
            database="analytics",
            username="reader",
            password="secret",
        )
        assert isinstance(eng, CachableEngine)


class TestDisposeEngine:
    """dispose_engine 方法测试"""

    def test_dispose_removes_from_cache(self):
        """释放后指定 ds_id 应不再缓存"""
        mgr = ConnectionPoolManager()
        mgr.get_engine(
            ds_id=1,
            ds_type="MYSQL",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password="password",
        )
        assert 1 in ConnectionPoolManager._engines

        mgr.dispose_engine(ds_id=1)
        assert 1 not in ConnectionPoolManager._engines

    def test_dispose_nonexistent_does_not_raise(self):
        """释放不存在的连接池不应抛异常"""
        mgr = ConnectionPoolManager()
        mgr.dispose_engine(ds_id=999)  # must not raise

    def test_dispose_one_engine_keeps_others(self):
        """释放一个数据源不应影响其他数据源"""
        mgr = ConnectionPoolManager()
        mgr.get_engine(
            ds_id=1,
            ds_type="MYSQL",
            host="localhost",
            port=3306,
            database="db1",
            username="root",
            password="pass",
        )
        mgr.get_engine(
            ds_id=2,
            ds_type="POSTGRESQL",
            host="localhost",
            port=5432,
            database="db2",
            username="user",
            password="pass",
        )
        mgr.dispose_engine(ds_id=1)
        assert 1 not in ConnectionPoolManager._engines
        assert 2 in ConnectionPoolManager._engines


class TestDisposeAll:
    """dispose_all 方法测试"""

    def test_dispose_all_clears_all(self):
        """释放所有连接池后 _engines 应为空"""
        mgr = ConnectionPoolManager()
        mgr.get_engine(
            ds_id=1,
            ds_type="MYSQL",
            host="h1",
            port=3306,
            database="d1",
            username="u",
            password="p",
        )
        mgr.get_engine(
            ds_id=2,
            ds_type="POSTGRESQL",
            host="h2",
            port=5432,
            database="d2",
            username="u",
            password="p",
        )
        mgr.get_engine(
            ds_id=3,
            ds_type="MYSQL",
            host="h3",
            port=3306,
            database="d3",
            username="u",
            password="p",
        )
        assert len(ConnectionPoolManager._engines) == 3

        mgr.dispose_all()
        assert len(ConnectionPoolManager._engines) == 0

    def test_dispose_all_empty_cache(self):
        """缓存为空时 dispose_all 不应抛异常"""
        mgr = ConnectionPoolManager()
        mgr.dispose_all()  # must not raise

    def test_dispose_all_called_twice(self):
        """连续两次调用 dispose_all 应安全"""
        mgr = ConnectionPoolManager()
        mgr.get_engine(
            ds_id=1,
            ds_type="MYSQL",
            host="h",
            port=3306,
            database="d",
            username="u",
            password="p",
        )
        mgr.dispose_all()
        mgr.dispose_all()  # second call must not raise
        assert len(ConnectionPoolManager._engines) == 0
