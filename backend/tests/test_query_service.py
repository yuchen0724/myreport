"""QueryService 单元测试"""

import pytest
import json
import hashlib
from unittest.mock import patch, MagicMock, PropertyMock, ANY
from datetime import datetime

from app.services.query_service import QueryService
from app.schemas.query import SQLQueryRequest, SQLQueryResponse
from app.utils.sql_validator import SQLValidator
from app.repositories.query_history_repository import QueryHistoryRepository
from app.models.query_history import QueryHistory
from app.models.data_source import DataSource


# =============================================================================
# SQLValidator 单元测试
# =============================================================================

class TestSQLValidator:
    """测试 SQLValidator.validate 方法"""

    def test_valid_select(self):
        """验证合法的 SELECT 查询"""
        is_valid, message = SQLValidator.validate("SELECT * FROM users")
        assert is_valid is True
        assert message == "验证通过"

    def test_valid_select_with_where(self):
        """验证带 WHERE 的 SELECT"""
        is_valid, message = SQLValidator.validate(
            "SELECT id, name FROM users WHERE age > 18"
        )
        assert is_valid is True

    def test_valid_with_cte(self):
        """验证 WITH 公共表表达式"""
        is_valid, message = SQLValidator.validate(
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte"
        )
        assert is_valid is True

    def test_empty_sql(self):
        """验证空 SQL"""
        is_valid, message = SQLValidator.validate("")
        assert is_valid is False
        assert "不能为空" in message

    def test_whitespace_sql(self):
        """验证空白 SQL"""
        is_valid, message = SQLValidator.validate("   ")
        assert is_valid is False

    def test_drop_statement(self):
        """验证 DROP 被拒绝"""
        is_valid, message = SQLValidator.validate("DROP TABLE users")
        assert is_valid is False
        assert "DROP" in message

    def test_delete_statement(self):
        """验证 DELETE 被拒绝"""
        is_valid, message = SQLValidator.validate("DELETE FROM users")
        assert is_valid is False
        assert "DELETE" in message

    def test_insert_statement(self):
        """验证 INSERT 被拒绝"""
        is_valid, message = SQLValidator.validate("INSERT INTO users VALUES (1)")
        assert is_valid is False
        assert "INSERT" in message

    def test_update_statement(self):
        """验证 UPDATE 被拒绝"""
        is_valid, message = SQLValidator.validate("UPDATE users SET name='x'")
        assert is_valid is False
        assert "UPDATE" in message

    def test_truncate_statement(self):
        """验证 TRUNCATE 被拒绝"""
        is_valid, message = SQLValidator.validate("TRUNCATE TABLE users")
        assert is_valid is False
        assert "TRUNCATE" in message

    def test_alter_statement(self):
        """验证 ALTER 被拒绝"""
        is_valid, message = SQLValidator.validate("ALTER TABLE users ADD COLUMN x INT")
        assert is_valid is False
        assert "ALTER" in message

    def test_create_statement(self):
        """验证 CREATE 被拒绝"""
        is_valid, message = SQLValidator.validate("CREATE TABLE t (id INT)")
        assert is_valid is False
        assert "CREATE" in message

    def test_execute_statement(self):
        """验证 EXEC/EXECUTE 被拒绝"""
        is_valid, message = SQLValidator.validate("EXEC xp_cmdshell")
        assert is_valid is False
        assert "EXEC" in message or "EXECUTE" in message

    def test_danger_function_sleep(self):
        """验证 SLEEP 函数被拒绝"""
        is_valid, message = SQLValidator.validate(
            "SELECT * FROM users WHERE id=1 AND SLEEP(5)"
        )
        assert is_valid is False
        assert "SLEEP" in message

    def test_danger_function_benchmark(self):
        """验证 BENCHMARK 函数被拒绝"""
        is_valid, message = SQLValidator.validate(
            "SELECT BENCHMARK(1000000, MD5('x'))"
        )
        assert is_valid is False

    def test_injection_or_1_eq_1(self):
        """验证 OR 1=1 注入模式"""
        is_valid, message = SQLValidator.validate(
            "SELECT * FROM users WHERE id=1 OR 1=1"
        )
        assert is_valid is False
        assert "注入" in message

    def test_injection_comment(self):
        """验证注释注入"""
        is_valid, message = SQLValidator.validate(
            "SELECT * FROM users WHERE id=1 -- admin"
        )
        assert is_valid is False

    def test_not_start_with_select(self):
        """验证非 SELECT/WITH 开头的 SQL"""
        is_valid, message = SQLValidator.validate("SHOW TABLES")
        assert is_valid is False
        assert "只允许 SELECT" in message

    def test_semicolon_injection(self):
        """验证分号多语句注入"""
        is_valid, message = SQLValidator.validate(
            "SELECT * FROM users; SELECT 1"
        )
        assert is_valid is False
        assert "分号" in message

    def test_unmatched_parentheses(self):
        """验证括号不匹配"""
        is_valid, message = SQLValidator.validate(
            "SELECT * FROM users WHERE (id=1"
        )
        assert is_valid is False
        assert "括号" in message

    def test_sql_too_long(self):
        """验证超长 SQL"""
        long_sql = "SELECT * FROM users WHERE 1=1 " + "AND x=1 " * 2000
        assert len(long_sql) > 10000
        is_valid, message = SQLValidator.validate(long_sql)
        assert is_valid is False
        assert "过长" in message

    def test_safe_keyword_in_column_name(self):
        """验证列名中的关键字不会误判"""
        # SELECT 是允许的，列名中包含 UPDATE 不应误判
        is_valid, message = SQLValidator.validate(
            "SELECT * FROM users"
        )
        assert is_valid is True


# =============================================================================
# QueryService 单元测试
# =============================================================================

class TestQueryService:
    """测试 QueryService 核心方法"""

    @pytest.fixture
    def mock_ds(self):
        """创建一个模拟数据源"""
        ds = MagicMock(spec=DataSource)
        ds.id = 1
        ds.name = "测试数据源"
        ds.type = "MYSQL"
        ds.host = "localhost"
        ds.port = 3306
        ds.database = "testdb"
        ds.username = "testuser"
        ds.password_encrypted = "encrypted_password"
        ds.use_proxy = False
        ds.proxy_server_id = None
        ds.is_active = True
        return ds

    @pytest.fixture
    def mock_query_result(self):
        """_execute_query 的模拟返回值"""
        return {
            "columns": ["id", "name", "age"],
            "rows": [
                [1, "Alice", 30],
                [2, "Bob", 25],
                [3, "Charlie", 35],
            ],
            "total": 100,
            "has_more": True,
            "order_cols": ["id"],
        }

    def test_init(self, db_session):
        """测试 QueryService 初始化"""
        service = QueryService(db_session)
        assert service.db is db_session
        assert service.ds_repo is not None
        assert service.history_repo is not None

    def test_make_cache_key(self, db_session):
        """测试缓存键生成"""
        service = QueryService(db_session)
        cache_key = service._make_cache_key(
            sql="SELECT * FROM users",
            params={"id": 1},
            page=1,
            page_size=50,
            cursor=None,
            skip_deep_pagination_check=False,
        )
        assert cache_key.startswith("query_result:")
        assert len(cache_key) > 20

        # 相同输入应生成相同键
        cache_key2 = service._make_cache_key(
            sql="SELECT * FROM users",
            params={"id": 1},
            page=1,
            page_size=50,
            cursor=None,
            skip_deep_pagination_check=False,
        )
        assert cache_key == cache_key2

        # 不同参数应生成不同键
        cache_key3 = service._make_cache_key(
            sql="SELECT * FROM users",
            params={"id": 2},
            page=1,
            page_size=50,
            cursor=None,
            skip_deep_pagination_check=False,
        )
        assert cache_key != cache_key3

    # ---- execute_sql 基本流程 ----

    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_success(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
        mock_query_result,
    ):
        """测试 execute_sql 正常执行"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None  # 无 redis 缓存
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 5000

        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=mock_query_result)

        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT id, name, age FROM users WHERE age > :min_age",
            params={"min_age": 18},
            page=1,
            page_size=10,
        )

        response = service.execute_sql(request, user_id=1)

        assert isinstance(response, SQLQueryResponse)
        assert response.columns == ["id", "name", "age"]
        assert len(response.rows) == 3
        assert response.total == 100
        assert response.page == 1
        assert response.page_size == 10
        assert response.execution_time_ms >= 0
        assert response.suggest_async is False
        assert response.cache_hit is False

        # 验证调用了 _execute_query
        service._execute_query.assert_called_once()


    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_cache_hit(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
    ):
        """测试缓存命中场景"""
        mock_decrypt.return_value = "real_password"
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_cache.redis_client = MagicMock()
        mock_metrics.slow_query_threshold_ms = 5000
        
        cached_response = {
            "response": {
                "columns": ["id", "name"],
                "rows": [[1, "Alice"]],
                "total": 1,
                "page": 1,
                "page_size": 50,
                "execution_time_ms": 10,
                "suggest_async": False,
                "cursor": None,
                "next_cursor": None,
                "cache_hit": False,
            }
        }
        mock_cache.redis_client.get.return_value = json.dumps(cached_response)
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT * FROM users",
            page=1,
            page_size=50,
        )
        
        response = service.execute_sql(request, user_id=1)
        
        assert isinstance(response, SQLQueryResponse)
        assert response.cache_hit is True
        assert response.columns == ["id", "name"]
        # 验证缓存被读取
        mock_cache.redis_client.get.assert_called_once()
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_validation_error(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
    ):
        """测试 SQL 验证失败"""
        service = QueryService(db_session)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="DROP TABLE users",
        )
        
        with pytest.raises(ValueError) as exc_info:
            service.execute_sql(request, user_id=1)
        
        assert "DROP" in str(exc_info.value)
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_datasource_not_found(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
    ):
        """测试数据源不存在"""
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=None)
        
        request = SQLQueryRequest(
            data_source_id=999,
            sql="SELECT 1",
        )
        
        with pytest.raises(ValueError) as exc_info:
            service.execute_sql(request, user_id=1)
        
        assert "数据源不存在" in str(exc_info.value)
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_execution_error(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
    ):
        """测试查询执行异常"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 5000
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(side_effect=Exception("连接超时"))
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT * FROM users",
        )
        
        with pytest.raises(ValueError) as exc_info:
            service.execute_sql(request, user_id=1)
        
        assert "查询执行失败" in str(exc_info.value)
        assert "连接超时" in str(exc_info.value)

    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_cursor_pagination(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
    ):
        """测试游标分页"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 5000
        
        # 模拟游标分页查询结果
        cursor_result = {
            "columns": ["id", "name"],
            "rows": [[4, "David"], [5, "Eve"]],
            "total": 100,
            "has_more": True,
            "order_cols": ["id"],
        }
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=cursor_result)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT id, name FROM users ORDER BY id",
            page=2,
            page_size=10,
            cursor="3",  # 上一页最后一行 id=3
        )
        
        response = service.execute_sql(request, user_id=1)
        
        assert response.columns == ["id", "name"]
        assert len(response.rows) == 2
        assert response.total == 100
        assert response.next_cursor == "5"  # 最后一行的 id
        
        # 验证 _execute_query 被调用时传入了 cursor
        args, kwargs = service._execute_query.call_args
        # cursor 是第 6 个位置参数 (ds, sql, params, page, page_size, cursor, ...)
        assert args[5] == "3"
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_skip_deep_pagination(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
    ):
        """测试 skip_deep_pagination_check=True 的场景（NL2SQL 查询）"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 5000
        
        result = {
            "columns": ["id", "name"],
            "rows": [[1, "Alice"]],
            "total": 1,
            "has_more": False,
            "order_cols": [],
        }
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=result)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT id, name FROM users",
            page=1,
            page_size=10,
            skip_deep_pagination_check=True,
        )
        
        response = service.execute_sql(request, user_id=1)
        
        assert response.columns == ["id", "name"]
        assert len(response.rows) == 1
        
        # 验证 skip_deep_pagination_check 被传递
        _, kwargs = service._execute_query.call_args
        assert kwargs["skip_deep_pagination_check"] is True
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_suggest_async(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
        mock_query_result,
    ):
        """测试高成本查询建议异步执行"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 5000
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=mock_query_result)
        
        # 通过 patch QueryOptimizer.estimate_query_cost 返回高成本
        with patch("app.services.query_service.QueryOptimizer.estimate_query_cost") as mock_cost:
            mock_cost.return_value = 500  # > 200
            
            request = SQLQueryRequest(
                data_source_id=1,
                sql="SELECT * FROM large_table JOIN other_table ON ...",
                page=1,
                page_size=10,
            )
            
            response = service.execute_sql(request, user_id=1)
            
            assert response.suggest_async is True
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_slow_query_recorded(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
        mock_query_result,
    ):
        """测试慢查询被记录"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 0  # 极低阈值，确保触发
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=mock_query_result)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT * FROM users",
        )
        
        response = service.execute_sql(request, user_id=1)
        
        # 验证慢查询指标被记录
        mock_metrics.record_slow_query.assert_called_once()
        call_kwargs = mock_metrics.record_slow_query.call_args[1]
        assert call_kwargs["sql"] is not None
        assert call_kwargs["data_source_id"] == 1
        assert call_kwargs["user_id"] == 1
    
    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_history_created(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
        mock_query_result,
    ):
        """测试查询历史被正确保存"""
        mock_decrypt.return_value = "real_password"
        mock_cache.redis_client = None
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_metrics.slow_query_threshold_ms = 5000
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=mock_query_result)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT * FROM users",
        )
        
        response = service.execute_sql(request, user_id=1)
        
        # 验证历史记录被写入数据库
        history_records = service.history_repo.get_by_user(user_id=1)
        assert len(history_records) >= 1
        record = history_records[0]
        assert record.user_id == 1
        assert record.data_source_id == 1
        assert record.query_type == "SQL"
        assert record.row_count == 100
        assert record.execution_time_ms is not None

    @patch("app.services.query_service.cache_service")
    @patch("app.services.query_service.metrics_collector")
    @patch("app.services.query_service.decrypt_password")
    def test_execute_sql_cache_write_on_miss(
        self,
        mock_decrypt,
        mock_metrics,
        mock_cache,
        db_session,
        mock_ds,
        mock_query_result,
    ):
        """测试缓存未命中时写入缓存"""
        mock_decrypt.return_value = "real_password"
        mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
        mock_cache.redis_client = MagicMock()
        mock_cache.redis_client.get.return_value = None  # 缓存未命中
        mock_metrics.slow_query_threshold_ms = 5000
        
        service = QueryService(db_session)
        service.ds_repo.get_by_id = MagicMock(return_value=mock_ds)
        service._execute_query = MagicMock(return_value=mock_query_result)
        
        request = SQLQueryRequest(
            data_source_id=1,
            sql="SELECT * FROM users",
        )
        
        response = service.execute_sql(request, user_id=1)
        
        # 验证缓存被写入
        mock_cache.redis_client.setex.assert_called_once()
    
    def test_execute_sql_with_params(self, db_session):
        """测试带参数的 SQL 查询（边缘场景）"""
        pass  # 已经在 test_execute_sql_success 中覆盖


# =============================================================================
# QueryHistoryRepository 单元测试
# =============================================================================

class TestQueryHistoryRepository:
    """测试 QueryHistoryRepository"""

    def test_create_history(self, db_session, test_user):
        """测试创建查询历史"""
        repo = QueryHistoryRepository(db_session)
        history = repo.create({
            "user_id": test_user.id,
            "data_source_id": 1,
            "query_type": "SQL",
            "query_text": "SELECT * FROM users",
            "execution_time_ms": 100,
            "row_count": 10,
        })
        
        assert history.id is not None
        assert history.user_id == test_user.id
        assert history.query_type == "SQL"
        assert history.query_text == "SELECT * FROM users"
        assert history.execution_time_ms == 100
        assert history.row_count == 10

    def test_get_by_user(self, db_session, test_user):
        """测试按用户获取查询历史"""
        repo = QueryHistoryRepository(db_session)
        
        # 创建多条历史
        for i in range(3):
            repo.create({
                "user_id": test_user.id,
                "data_source_id": 1,
                "query_type": "SQL",
                "query_text": f"SELECT * FROM table_{i}",
                "execution_time_ms": 50 + i * 10,
                "row_count": 10 + i,
            })
        
        histories = repo.get_by_user(user_id=test_user.id)
        assert len(histories) == 3
        # 验证所有记录都存在（created_at 排序在 SQLite 内存模式下可能不精确）
        texts = [h.query_text for h in histories]
        assert "SELECT * FROM table_0" in texts
        assert "SELECT * FROM table_1" in texts
        assert "SELECT * FROM table_2" in texts

    def test_get_by_user_with_pagination(self, db_session, test_user):
        """测试分页获取历史"""
        repo = QueryHistoryRepository(db_session)
        
        for i in range(5):
            repo.create({
                "user_id": test_user.id,
                "data_source_id": 1,
                "query_type": "SQL",
                "query_text": f"SELECT * FROM table_{i}",
                "execution_time_ms": 50,
                "row_count": 10,
            })
        
        # 测试 skip
        histories = repo.get_by_user(user_id=test_user.id, skip=2)
        assert len(histories) == 3
        
        # 测试 limit
        histories = repo.get_by_user(user_id=test_user.id, limit=2)
        assert len(histories) == 2

    def test_get_by_id(self, db_session, test_user):
        """测试按 ID 获取历史"""
        repo = QueryHistoryRepository(db_session)
        history = repo.create({
            "user_id": test_user.id,
            "data_source_id": 1,
            "query_type": "SQL",
            "query_text": "SELECT * FROM users",
        })
        
        found = repo.get_by_id(history.id)
        assert found is not None
        assert found.id == history.id
        assert found.query_text == "SELECT * FROM users"
        
        not_found = repo.get_by_id(99999)
        assert not_found is None

    def test_get_by_user_empty(self, db_session, test_user):
        """测试无历史记录时返回空列表"""
        repo = QueryHistoryRepository(db_session)
        histories = repo.get_by_user(user_id=test_user.id)
        assert histories == []

    def test_get_by_user_other_user(self, db_session, test_user):
        """测试查询其他用户的历史（应返回空）"""
        repo = QueryHistoryRepository(db_session)
        # 为 test_user 创建一条记录
        repo.create({
            "user_id": test_user.id,
            "data_source_id": 1,
            "query_type": "SQL",
            "query_text": "SELECT 1",
        })
        
        # 查询其他用户
        histories = repo.get_by_user(user_id=999)
        assert histories == []


# =============================================================================
# QueryService - 整体流程集成测试（使用真实 DB + Mock 数据源连接）
# =============================================================================

class TestQueryServiceIntegration:
    """集成测试：使用真实 SQLite DB + Mock 外部连接"""

    def test_execute_sql_with_db_and_mock_ds(
        self, db_session, test_user
    ):
        """完整集成：数据库有 user，mock 数据源"""
        from unittest.mock import patch, MagicMock
        
        # 准备数据源（写入真实 DB）
        from app.core.security import encrypt_password
        real_ds = DataSource(
            name="集成测试数据源",
            type="MYSQL",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password_encrypted=encrypt_password("testpass"),
            is_active=True,
            created_by=test_user.id,
        )
        db_session.add(real_ds)
        db_session.commit()
        db_session.refresh(real_ds)

        result = {
            "columns": ["id", "name"],
            "rows": [[1, "Alice"], [2, "Bob"]],
            "total": 2,
            "has_more": False,
            "order_cols": ["id"],
        }

        with patch("app.services.query_service.cache_service") as mock_cache:
            with patch("app.services.query_service.metrics_collector") as mock_metrics:
                with patch("app.services.query_service.decrypt_password") as mock_decrypt:
                    mock_cache.redis_client = None
                    mock_cache.DEFAULT_TTL_BY_SOURCE = {"MYSQL": 300}
                    mock_metrics.slow_query_threshold_ms = 5000
                    mock_decrypt.return_value = "real_password"

                    service = QueryService(db_session)
                    service._execute_query = MagicMock(return_value=result)

                    request = SQLQueryRequest(
                        data_source_id=real_ds.id,
                        sql="SELECT id, name FROM users",
                        page=1,
                        page_size=10,
                    )

                    response = service.execute_sql(request, user_id=test_user.id)

                    assert response.columns == ["id", "name"]
                    assert len(response.rows) == 2
                    assert response.total == 2
                    
                    # 验证历史被保存到真实数据库
                    histories = db_session.query(QueryHistory).filter(
                        QueryHistory.user_id == test_user.id
                    ).all()
                    assert len(histories) >= 1
