"""数据库全量查询执行器 - 直接返回行+列格式数据"""

import logging
from contextlib import contextmanager
from typing import Optional, Tuple, Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from app.core.security import decrypt_password

logger = logging.getLogger(__name__)

# PySocks 可选依赖
try:
    import socks as _socks
    _HAS_SOCKS = True
except ImportError:
    _HAS_SOCKS = False


def build_pymysql_socks_creator(
    *,
    proxy_host: str,
    proxy_port: int,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    connect_timeout: int = 30,
    read_timeout: int = 300,
):
    """Build a DBAPI creator whose socket is scoped to one MySQL connection."""
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")

    import pymysql

    def _creator():
        sock = _socks.socksocket()
        sock.set_proxy(_socks.SOCKS5, proxy_host, proxy_port)
        sock.settimeout(connect_timeout)
        connection = pymysql.connections.Connection(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            defer_connect=True,
        )
        try:
            sock.connect((host, port))
            connection.connect(sock)
            return connection
        except BaseException:
            sock.close()
            raise

    return _creator


# ── SOCKS5 代理统一方案 ──────────────────────────────────────────

def _get_proxy_info(ds, db_session=None):
    """
    从数据源配置中提取 SOCKS5 代理信息。

    Args:
        ds: 数据源对象（需有 use_proxy / proxy_server_id 属性）
        db_session: 可选现有 DB session

    Returns:
        dict 包含 host/port，或 None（未配置/不可用）
    """
    if not getattr(ds, 'use_proxy', False) or not getattr(ds, 'proxy_server_id', None):
        return None
    try:
        from app.models.proxy_server import ProxyServer
        if db_session is not None:
            proxy = db_session.query(ProxyServer).filter(
                ProxyServer.id == ds.proxy_server_id
            ).first()
        else:
            from app.core.database import SessionLocal
            _temp_db = SessionLocal()
            try:
                proxy = _temp_db.query(ProxyServer).filter(
                    ProxyServer.id == ds.proxy_server_id
                ).first()
            finally:
                _temp_db.close()

        if proxy and proxy.is_active and proxy.proxy_type.lower() == 'socks5':
            return {"host": proxy.host, "port": proxy.port}
    except Exception as e:
        logger.warning(f"[代理] 获取代理配置失败: {e}")
    return None


# ── 正确的 SOCKS5 方案：临时 socket 补丁（pymysql + SOCKS5 标准做法） ──

@contextmanager
def socks5_patch(proxy_host: str, proxy_port: int, timeout: int = 60):
    """Reject the legacy process-wide socket monkeypatch."""
    raise RuntimeError("socks5_patch 已停用，请使用 build_pymysql_socks_creator")
    yield  # pragma: no cover


def create_socks5_engine(url: str, proxy_host: str, proxy_port: int, **engine_kwargs) -> Tuple[Any, bool]:
    """
    创建带 SOCKS5 代理的 SQLAlchemy engine。

    适用于需要长期持有 engine 的场景（如连接池管理）。
    返回 (engine, use_socks)。

    注意：engine 是懒连接，实际连接时 pool 会创建新 socket。
    如果 engine 需要跨请求复用，调用方必须确保每次 checkout 连接时
    socks5_patch 上下文仍然生效。对于长期缓存的 engine，建议配合
    PoolListener 使用，或使用 ConnectionPoolManager 提供的代理支持。

    Args:
        url: 数据库连接 URL
        proxy_host: SOCKS5 代理主机
        proxy_port: SOCKS5 代理端口
        **engine_kwargs: 透传给 create_engine 的其他参数
    """
    raise RuntimeError("create_socks5_engine 已停用，请使用 DataSourceEngineFactory")


def socks5_pool_workaround(proxy_host: str, proxy_port: int):
    """
    [线程安全] 返回 (attach_fn, detach_fn) 用于给 engine 绑定 SOCKS5 补丁。
    通过引用计数避免多线程 checkout/checkin 竞争。

    用法：
        attach, _ = socks5_pool_workaround(host, port)
        engine = create_engine(url)
        attach(engine)
    """
    raise RuntimeError("socks5_pool_workaround 已停用，请使用 build_pymysql_socks_creator")


# ── 兼容层：旧函数保留供外部引用 ──────────────────────────────

@contextmanager
def socks_proxy_context(ds, db_session=None, timeout: int = 60):
    """
    全局 socket 补丁上下文管理器 — 自动根据数据源配置打补丁。

    新版使用 socks5_patch() 直接指定 host/port。
    本函数保留供外部（如nl2sql/schema.py）调用。

    Yields: (use_socks: bool)
    """
    proxy_info = _get_proxy_info(ds, db_session)
    use_socks = proxy_info is not None
    if use_socks:
        raise RuntimeError("socks_proxy_context 已停用，请使用 DataSourceEngineFactory")
    else:
        yield False


def setup_socks(ds, db_session=None, timeout: int = 60):
    """[兼容存根] 旧版 proxy setup 函数。"""
    _get_proxy_info(ds, db_session)
    return lambda: None


def _apply_socks_proxy(proxy_host: str, proxy_port: int, timeout: int = 60):
    """Reject the legacy process-wide socket replacement."""
    raise RuntimeError("_apply_socks_proxy 已停用，请使用 build_pymysql_socks_creator")


def _restore_socket():
    """No-op retained for import compatibility."""


def _restore_socket_cm():
    """[兼容存根]"""
    pass


def _build_socks_creator(proxy_host: str, proxy_port: int, timeout: int = 60):
    """
    [已弃用 - 保留供外部引用] SOCKS5 creator 不适用于 pymysql。
    请改用 socks5_patch() 上下文管理器。
    """
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")
    def _creator():
        s = _socks.socksocket()
        s.settimeout(timeout)
        s.set_proxy(_socks.SOCKS5, proxy_host, proxy_port)
        return s
    return _creator


def create_socks_engine(url: str, proxy_host: str, proxy_port: int, **engine_kwargs) -> Tuple[Any, bool]:
    """
    [已弃用 - 保留供外部引用] 旧版 creator 方式不适用于 pymysql。
    请改用 create_socks5_engine() 或 socks5_patch() 上下文管理器 + create_engine。
    """
    logger.warning("create_socks_engine 已弃用，请使用 create_socks5_engine")
    return create_socks5_engine(url, proxy_host, proxy_port, **engine_kwargs)


def setup_proxy_for_ds(ds, timeout: int = 60) -> tuple:
    """[兼容存根] 旧版 proxy 设置函数。"""
    use_socks = _get_proxy_info(ds) is not None
    return None, use_socks


def restore_socket(original_socket):
    """[兼容存根]"""
    pass


# ── 查询执行器 ──────────────────────────────────────────────────

def execute_query(ds, sql: str) -> tuple:
    """
    执行查询并返回 (rows, columns)
    支持数据源配置的 SOCKS5 代理（use_proxy + proxy_server_id）。
    """
    from sqlalchemy.exc import OperationalError
    import time
    from urllib.parse import quote_plus

    password = decrypt_password(ds.password_encrypted)
    ds_type = ds.type.upper() if ds.type else "DORIS"

    # URL 编码密码中的特殊字符
    encoded_password = quote_plus(password)

    if ds_type == "POSTGRESQL":
        conn_url = f"postgresql://{ds.username}:{encoded_password}@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type in ("MYSQL", "DORIS"):
        conn_url = f"mysql+pymysql://{ds.username}:{encoded_password}@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type == "HIVE":
        conn_url = f"hive://{ds.username}:{encoded_password}@{ds.host}:{ds.port}/{ds.database}"
    else:
        raise ValueError(f"不支持的数据源类型: {ds.type}")

    connect_args = {}
    if ds_type == "POSTGRESQL":
        connect_args["connect_timeout"] = 30
    else:
        connect_args["connect_timeout"] = 30
        connect_args["read_timeout"] = 300

    # 确定是否需要 SOCKS5 代理
    proxy_info = _get_proxy_info(ds)
    engine = None
    max_retries = 2
    try:
        for attempt in range(max_retries):
            try:
                if proxy_info:
                    if ds_type not in ("MYSQL", "DORIS"):
                        raise ValueError("SOCKS5 代理当前仅支持 MySQL/Doris 数据源")
                    logger.info(f"[查询] 使用 SOCKS5 代理: {proxy_info['host']}:{proxy_info['port']}")
                    creator = build_pymysql_socks_creator(
                        proxy_host=proxy_info['host'], proxy_port=proxy_info['port'],
                        host=ds.host, port=ds.port, username=ds.username,
                        password=password, database=ds.database,
                        connect_timeout=30, read_timeout=300,
                    )
                    engine = create_engine(
                        conn_url, poolclass=QueuePool, pool_size=2, max_overflow=4,
                        creator=creator,
                    )
                else:
                    engine = create_engine(
                        conn_url, poolclass=QueuePool, pool_size=2, max_overflow=4,
                        connect_args=connect_args,
                    )
                with engine.connect() as conn:
                    result = conn.execute(text(sql))
                    columns = list(result.keys())
                    rows = _fetch_all(result, batch_size=100000)
                    return rows, columns
            except OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise ValueError(f"查询执行失败: {e}")
    finally:
        try:
            if engine is not None:
                engine.dispose()
        except Exception:
            pass


def _fetch_all(result, batch_size: int = 100000) -> list:
    """分批从 result 中取出所有行"""
    rows = []
    while True:
        batch = result.fetchmany(batch_size)
        if not batch:
            break
        rows.extend([list(row) for row in batch])
    return rows
