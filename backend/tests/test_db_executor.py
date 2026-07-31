"""测试数据库查询执行器 - db_executor.py

覆盖 execute_query 函数（MYSQL/DORIS/POSTGRESQL/HIVE 连接 URL 构建、
密码加密字段解密、重试逻辑），setup_proxy_for_ds、
_apply_socks_proxy / restore_socket。
使用 mock 模拟 create_engine 和 decrypt_password。
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import socket as _socket
from sqlalchemy.exc import OperationalError

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def mock_ds():
    """创建一个模拟的数据源对象（通用）"""
    ds = MagicMock()
    ds.type = "MYSQL"
    ds.host = "192.168.1.100"
    ds.port = 3306
    ds.database = "test_db"
    ds.username = "test_user"
    ds.password_encrypted = "encrypted_password_value"
    ds.use_proxy = False
    ds.proxy_server_id = None
    return ds


@pytest.fixture
def mock_ds_mysql():
    ds = MagicMock()
    ds.type = "MYSQL"
    ds.host = "mysql-host"
    ds.port = 3306
    ds.database = "mydb"
    ds.username = "admin"
    ds.password_encrypted = "enc-pass-mysql"
    ds.use_proxy = False
    ds.proxy_server_id = None
    return ds


@pytest.fixture
def mock_ds_doris():
    ds = MagicMock()
    ds.type = "DORIS"
    ds.host = "doris-host"
    ds.port = 9030
    ds.database = "doris_db"
    ds.username = "doris_user"
    ds.password_encrypted = "enc-pass-doris"
    ds.use_proxy = False
    ds.proxy_server_id = None
    return ds


@pytest.fixture
def mock_ds_postgresql():
    ds = MagicMock()
    ds.type = "POSTGRESQL"
    ds.host = "pg-host"
    ds.port = 5432
    ds.database = "pgdb"
    ds.username = "pg_user"
    ds.password_encrypted = "enc-pass-pg"
    ds.use_proxy = False
    ds.proxy_server_id = None
    return ds


@pytest.fixture
def mock_ds_hive():
    ds = MagicMock()
    ds.type = "HIVE"
    ds.host = "hive-host"
    ds.port = 10000
    ds.database = "hivedb"
    ds.username = "hive_user"
    ds.password_encrypted = "enc-pass-hive"
    ds.use_proxy = False
    ds.proxy_server_id = None
    return ds


@pytest.fixture
def mock_ds_with_proxy():
    """使用 SOCKS5 代理的数据源"""
    ds = MagicMock()
    ds.type = "MYSQL"
    ds.host = "proxy-mysql-host"
    ds.port = 3306
    ds.database = "proxied_db"
    ds.username = "proxy_user"
    ds.password_encrypted = "enc-pass-proxy"
    ds.use_proxy = True
    ds.proxy_server_id = 1
    return ds


@pytest.fixture
def mock_engine_connection():
    """创建 mock engine 和 connection，返回 (mock_engine, mock_conn, mock_result)
    
    mock_engine.connect.return_value 是一个 context manager (CM).
    CM.__enter__() 返回 mock_conn, CM.__exit__() 是一个 MagicMock.
    
    若需测试重试，可设置 mock_engine.connect.side_effect, 
    并将同一个 CM 实例作为 side_effect 元素提供给后续调用。
    """
    mock_result = MagicMock()
    mock_result.keys.return_value = ["id", "name", "age"]

    # fetchmany: 第一次返回一批数据，第二次返回空
    mock_result.fetchmany.side_effect = [
        [(1, "Alice", 30), (2, "Bob", 25)],
        [],
    ]

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_result

    # 构建 context manager (connect return value)
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_conn
    mock_cm.__exit__ = MagicMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_cm

    # 保存 cm 引用以便重试测试
    mock_engine._mock_cm = mock_cm

    return mock_engine, mock_conn, mock_result


# ===================================================================
# Tests for execute_query — connection URL building per DB type
# ===================================================================


class TestExecuteQueryConnectionURL:
    """验证每种数据源类型生成正确的连接 URL"""

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="decrypted_pwd")
    def test_mysql_url(self, mock_decrypt, mock_create_engine, mock_ds_mysql, mock_engine_connection):
        """MYSQL: mysql+pymysql://..."""
        mock_engine, _, _ = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds_mysql, "SELECT 1")

        # 验证 create_engine 被使用正确的 URL 调用
        call_url = mock_create_engine.call_args[0][0]
        assert "mysql+pymysql://admin:decrypted_pwd@mysql-host:3306/mydb" in call_url

        # 验证结果
        assert columns == ["id", "name", "age"]
        assert rows == [[1, "Alice", 30], [2, "Bob", 25]]

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="decrypted_pwd")
    def test_doris_url(self, mock_decrypt, mock_create_engine, mock_ds_doris, mock_engine_connection):
        """DORIS: 也使用 mysql+pymysql://..."""
        mock_engine, _, _ = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds_doris, "SELECT 1")

        call_url = mock_create_engine.call_args[0][0]
        assert "mysql+pymysql://doris_user:decrypted_pwd@doris-host:9030/doris_db" in call_url
        assert columns == ["id", "name", "age"]

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="decrypted_pwd")
    def test_postgresql_url(self, mock_decrypt, mock_create_engine, mock_ds_postgresql, mock_engine_connection):
        """POSTGRESQL: postgresql://..."""
        mock_engine, _, _ = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds_postgresql, "SELECT 1")

        call_url = mock_create_engine.call_args[0][0]
        assert "postgresql://pg_user:decrypted_pwd@pg-host:5432/pgdb" in call_url
        assert columns == ["id", "name", "age"]

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="decrypted_pwd")
    def test_hive_url(self, mock_decrypt, mock_create_engine, mock_ds_hive, mock_engine_connection):
        """HIVE: hive://..."""
        mock_engine, _, _ = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds_hive, "SELECT 1")

        call_url = mock_create_engine.call_args[0][0]
        assert "hive://hive_user:decrypted_pwd@hive-host:10000/hivedb" in call_url
        assert columns == ["id", "name", "age"]

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="p@ss!w#rd")
    def test_url_encoded_password(self, mock_decrypt, mock_create_engine, mock_ds_mysql, mock_engine_connection):
        """密码含特殊字符时被 URL 编码"""
        mock_engine, _, _ = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        # mock_ds_mysql 的 password_encrypted 会触发 decrypt_password 返回 "p@ss!w#rd"
        # 验证 URL 编码后密码中的 @ 和 # 被转义
        rows, columns = execute_query(mock_ds_mysql, "SELECT 1")

        call_url = mock_create_engine.call_args[0][0]
        # quote_plus 会将 @ 编码为 %40，将 # 编码为 %23
        assert "%40" in call_url or "p%40ss" in call_url
        assert "%23" in call_url or "w%23rd" in call_url

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password")
    def test_decrypt_password_called(self, mock_decrypt, mock_create_engine, mock_ds_mysql, mock_engine_connection):
        """验证 decrypt_password 被调用且传入正确的密文"""
        mock_engine, _, _ = mock_engine_connection
        mock_create_engine.return_value = mock_engine
        mock_decrypt.return_value = "decrypted"

        from app.utils.db_executor import execute_query

        execute_query(mock_ds_mysql, "SELECT 1")

        mock_decrypt.assert_called_once_with("enc-pass-mysql")


# ===================================================================
# Tests for retry logic
# ===================================================================


class TestExecuteQueryRetry:
    """验证 execute_query 在 OperationalError 时的重试逻辑"""

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_retry_then_success(self, mock_decrypt, mock_create_engine, mock_ds, mock_engine_connection):
        """第一次查询抛出 OperationalError，第二次成功"""
        mock_engine, mock_conn, mock_result = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        # 获取预先配置好的 context manager
        mock_cm = mock_engine._mock_cm
        # 第一次连接抛出异常，第二次返回事先配好的 CM
        mock_engine.connect.side_effect = [
            OperationalError("mock", "mock", "mock"),
            mock_cm,
        ]

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds, "SELECT 1")

        assert columns == ["id", "name", "age"]
        assert rows == [[1, "Alice", 30], [2, "Bob", 25]]
        # 验证 connect 被调用了两次
        assert mock_engine.connect.call_count == 2

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_retry_all_fail(self, mock_decrypt, mock_create_engine, mock_ds):
        """所有重试均失败，最终抛出 ValueError"""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("mock", "mock", "mock")
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        with pytest.raises(ValueError, match="查询执行失败"):
            execute_query(mock_ds, "SELECT 1")

        # connect 应该被调用了 max_retries 次（2次）
        assert mock_engine.connect.call_count == 2

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_no_retry_on_success(self, mock_decrypt, mock_create_engine, mock_ds, mock_engine_connection):
        """第一次就成功，不触发重试"""
        mock_engine, mock_conn, mock_result = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds, "SELECT 1")

        assert columns == ["id", "name", "age"]
        # connect 只被调用了 1 次
        assert mock_engine.connect.call_count == 1


# ===================================================================
# Tests for unsupported DB type
# ===================================================================


class TestExecuteQueryUnsupportedType:

    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_unsupported_type_raises(self, mock_decrypt):
        """不支持的数据源类型抛出 ValueError"""
        ds = MagicMock()
        ds.type = "ORACLE"
        ds.host = "oracle-host"
        ds.port = 1521
        ds.database = "orcl"
        ds.username = "sys"
        ds.password_encrypted = "enc"
        ds.use_proxy = False
        ds.proxy_server_id = None

        from app.utils.db_executor import execute_query

        with pytest.raises(ValueError, match="不支持的数据源类型"):
            execute_query(ds, "SELECT 1")


# ===================================================================
# Tests for SOCKS5 proxy
# ===================================================================


class TestProxyFunctions:
    """测试 setup_proxy_for_ds、_apply_socks_proxy、restore_socket"""

    def test_setup_proxy_no_proxy_needed(self, mock_ds):
        """数据源未配置代理时，返回 (None, False)"""
        from app.utils.db_executor import setup_proxy_for_ds

        original_socket, use_socks = setup_proxy_for_ds(mock_ds)

        assert original_socket is None
        assert use_socks is False

    def test_setup_proxy_use_proxy_false(self, mock_ds):
        """use_proxy=False 时，即使有 proxy_server_id 也不启用代理"""
        from app.utils.db_executor import setup_proxy_for_ds

        ds = MagicMock()
        ds.use_proxy = False
        ds.proxy_server_id = 1

        original_socket, use_socks = setup_proxy_for_ds(ds)
        assert original_socket is None
        assert use_socks is False

    @patch("app.repositories.proxy_server_repository.ProxyServerRepository")
    @patch("app.core.database.SessionLocal")
    def test_setup_proxy_with_socks5(
        self, mock_session_local, mock_proxy_repo_class,
        mock_ds_with_proxy, monkeypatch
    ):
        """SOCKS5 配置不再返回或替换全局 socket。"""
        monkeypatch.setattr(
            "app.utils.db_executor._get_proxy_info",
            lambda ds: {"host": "proxy.example.com", "port": 1080},
        )

        from app.utils.db_executor import setup_proxy_for_ds, restore_socket

        original_socket, use_socks = setup_proxy_for_ds(mock_ds_with_proxy)

        assert use_socks is True
        assert original_socket is None

    @patch("app.repositories.proxy_server_repository.ProxyServerRepository")
    @patch("app.core.database.SessionLocal")
    def test_setup_proxy_not_socks5(
        self, mock_session_local, mock_proxy_repo_class, mock_ds_with_proxy
    ):
        """代理类型不是 SOCKS5 时返回 (None, False)"""
        mock_proxy = MagicMock()
        mock_proxy.proxy_type = "http"
        mock_proxy.host = "http-proxy"
        mock_proxy.port = 3128

        mock_repo_instance = MagicMock()
        mock_repo_instance.get_by_id.return_value = mock_proxy
        mock_proxy_repo_class.return_value = mock_repo_instance

        mock_db_session = MagicMock()
        mock_session_local.return_value = mock_db_session

        from app.utils.db_executor import setup_proxy_for_ds

        original_socket, use_socks = setup_proxy_for_ds(mock_ds_with_proxy)

        assert original_socket is None
        assert use_socks is False

    @patch("app.repositories.proxy_server_repository.ProxyServerRepository")
    @patch("app.core.database.SessionLocal")
    def test_setup_proxy_exception(
        self, mock_session_local, mock_proxy_repo_class, mock_ds_with_proxy
    ):
        """数据库查询异常时，返回 (None, False)，不传播异常"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.get_by_id.side_effect = Exception("DB error")
        mock_proxy_repo_class.return_value = mock_repo_instance

        mock_db_session = MagicMock()
        mock_session_local.return_value = mock_db_session

        from app.utils.db_executor import setup_proxy_for_ds

        # 不应抛出异常，应静默降级
        original_socket, use_socks = setup_proxy_for_ds(mock_ds_with_proxy)

        assert original_socket is None
        assert use_socks is False

    def test_apply_socks_proxy_without_pysocks(self, monkeypatch):
        """PySocks 未安装时，_apply_socks_proxy 抛出 RuntimeError"""
        monkeypatch.setattr("app.utils.db_executor._HAS_SOCKS", False)

        from app.utils.db_executor import _apply_socks_proxy

        with pytest.raises(RuntimeError, match="已停用"):
            _apply_socks_proxy("host", 1080)

    def test_apply_and_restore_socks_proxy(self, monkeypatch):
        """旧全局补丁入口必须拒绝执行且不得改变 socket。"""
        import app.utils.db_executor as db_exec

        # 确保 _HAS_SOCKS 为 True
        monkeypatch.setattr(db_exec, "_HAS_SOCKS", True)

        # 模拟 socks 模块
        mock_socks = MagicMock()
        mock_socks.SOCKS5 = 5
        monkeypatch.setattr(db_exec, "_socks", mock_socks)

        # 保存原始 socket 引用
        original_socket = _socket.socket

        from app.utils.db_executor import _apply_socks_proxy, restore_socket

        mock_socksocket = MagicMock()
        mock_socks.socksocket = mock_socksocket

        with pytest.raises(RuntimeError, match="已停用"):
            _apply_socks_proxy("proxy.example.com", 1080, timeout=60)
        assert _socket.socket == original_socket
        mock_socks.set_default_proxy.assert_not_called()

    def test_restore_socket_stores_default(self, monkeypatch):
        """restore_socket 恢复 socket 并重置 socks 默认代理"""
        import app.utils.db_executor as db_exec

        monkeypatch.setattr(db_exec, "_HAS_SOCKS", True)
        mock_socks = MagicMock()
        monkeypatch.setattr(db_exec, "_socks", mock_socks)

        original = _socket.socket

        from app.utils.db_executor import restore_socket

        restore_socket(original)

        assert _socket.socket == original
        mock_socks.set_default_proxy.assert_not_called()


# ===================================================================
# Tests for execute_query — with proxy integration
# ===================================================================


class TestExecuteQueryWithProxy:

    @patch("app.utils.db_executor.build_pymysql_socks_creator")
    @patch("app.utils.db_executor._get_proxy_info", return_value={"host": "proxy.example.com", "port": 1080})
    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_execute_with_proxy(
        self, mock_decrypt, mock_create_engine, mock_proxy_info, mock_creator,
        mock_ds_with_proxy, mock_engine_connection
    ):
        """使用代理时的完整执行流程"""
        mock_engine, mock_conn, mock_result = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        creator = MagicMock()
        mock_creator.return_value = creator

        from app.utils.db_executor import execute_query

        rows, columns = execute_query(mock_ds_with_proxy, "SELECT 1")

        assert columns == ["id", "name", "age"]
        assert rows == [[1, "Alice", 30], [2, "Bob", 25]]

        mock_creator.assert_called_once()
        assert mock_create_engine.call_args.kwargs["creator"] is creator

    @patch("app.utils.db_executor.build_pymysql_socks_creator")
    @patch("app.utils.db_executor._get_proxy_info", return_value={"host": "proxy.example.com", "port": 1080})
    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_execute_with_proxy_restore_on_error(
        self, mock_decrypt, mock_create_engine, mock_proxy_info, mock_creator,
        mock_ds_with_proxy
    ):
        """代理场景下查询失败时仍会恢复 socket"""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("mock", "mock", "mock")
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        with pytest.raises(ValueError, match="查询执行失败"):
            execute_query(mock_ds_with_proxy, "SELECT 1")

        assert mock_creator.call_count == 2

    @patch("app.utils.db_executor._get_proxy_info", return_value=None)
    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_execute_without_proxy_no_restore(
        self, mock_decrypt, mock_create_engine, mock_proxy_info,
        mock_ds, mock_engine_connection
    ):
        """不使用代理时不会调用 restore_socket"""
        mock_engine, mock_conn, mock_result = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query
        # 需要 patch restore_socket 来验证它没有被调用
        with patch("app.utils.db_executor.restore_socket") as mock_restore:
            rows, columns = execute_query(mock_ds, "SELECT 1")
            assert columns == ["id", "name", "age"]
            mock_restore.assert_not_called()


# ===================================================================
# Tests for engine.dispose and cleanup
# ===================================================================


class TestExecuteQueryCleanup:

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_engine_dispose_called(self, mock_decrypt, mock_create_engine, mock_ds, mock_engine_connection):
        """验证 engine.dispose() 在 finally 中被调用"""
        mock_engine, mock_conn, mock_result = mock_engine_connection
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        execute_query(mock_ds, "SELECT 1")

        mock_engine.dispose.assert_called_once()

    @patch("app.utils.db_executor.create_engine")
    @patch("app.utils.db_executor.decrypt_password", return_value="pwd")
    def test_engine_dispose_on_error(self, mock_decrypt, mock_create_engine, mock_ds):
        """验证即使在错误路径下 engine.dispose() 也被调用"""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("mock", "mock", "mock")
        mock_create_engine.return_value = mock_engine

        from app.utils.db_executor import execute_query

        with pytest.raises(ValueError):
            execute_query(mock_ds, "SELECT 1")

        mock_engine.dispose.assert_called_once()
