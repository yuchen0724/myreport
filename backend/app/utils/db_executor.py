"""数据库全量查询执行器 - 直接返回行+列格式数据"""

import logging
import socket as _socket
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


# ── SOCKS5 代理统一方案 ──────────────────────────────────────────

# ═══ SOCKS5 代理 — engine 级别方案（无全局 socket 污染） ═══

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


def _build_socks_creator(proxy_host: str, proxy_port: int, timeout: int = 60):
    """返回一个 SOCKS5 感知的 connection creator 函数，用于 create_engine(creator=...)。"""
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")
    def _creator():
        s = _socks.socksocket()
        s.settimeout(timeout)
        s.set_proxy(_socks.SOCKS5, proxy_host, proxy_port)
        return s
    return _creator


@contextmanager
def socks_proxy_context(ds, db_session=None, timeout: int = 60):
    """
    [已弃用] 全局 socket 补丁上下文管理器 — 为向后兼容保留但不再打全局补丁。

    新版使用 engine 级别的 proxy creator（无全局副作用）。
    请使用 create_socks_engine() 或 DataSourceEngineFactory 的 proxy 支持。

    Args:
        ds: 数据源对象
        db_session: 可选现有 DB session
        timeout: socket 超时秒数

    Yields: (use_socks: bool) — 判断是否走了代理（不再实际设置代理）
    """
    use_socks = False
    if _get_proxy_info(ds, db_session) is not None:
        use_socks = True
        logger.debug(f"[代理] 数据源 {ds.id} 配置了 SOCKS5 代理")
    try:
        yield use_socks
    finally:
        pass  # 不再需要恢复 socket


def setup_socks(ds, db_session=None, timeout: int = 60):
    """
    [已弃用] 旧版 proxy setup 函数 — 返回空操作函数。

    新版使用 engine 级别的 proxy creator。
    """
    _get_proxy_info(ds, db_session)  # 仅用于日志记录
    return lambda: None


# ═══ 保留旧接口用于测试兼容（内部仍用 engine 级别方案） ═══

_original_global_socket = _socket.socket  # 保留引用


def _apply_socks_proxy(proxy_host: str, proxy_port: int, timeout: int = 60):
    """
    [已弃用] 旧版全局 socket 替换 — 仅用于向后兼容。
    请改用 create_socks_engine()。
    """
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")
    _socks.set_default_proxy(_socks.SOCKS5, proxy_host, proxy_port)
    _socket.socket = _socks.socksocket
    _socket.setdefaulttimeout(timeout)


def _restore_socket():
    """[已弃用] 旧版 socket 恢复 — 仅用于向后兼容。"""
    global _original_global_socket
    _socket.socket = _original_global_socket
    try:
        _socks.set_default_proxy()
    except Exception:
        pass


def _restore_socket_cm():
    """[已弃用保留兼容]"""
    pass


def create_socks_engine(url: str, proxy_host: str, proxy_port: int, **engine_kwargs) -> Tuple[Any, bool]:
    """
    创建带 SOCKS5 代理的 SQLAlchemy engine（通过 creator 参数，不污染全局 socket）。

    适用于需要长期持有 engine 的场景（如连接池管理）。
    返回 (engine, use_socks)。

    Args:
        url: 数据库连接 URL
        proxy_host: SOCKS5 代理主机
        proxy_port: SOCKS5 代理端口
        **engine_kwargs: 透传给 create_engine 的其他参数
    """
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")

    def _socks_creator():
        s = _socks.socksocket()
        s.settimeout(60)
        s.set_proxy(_socks.SOCKS5, proxy_host, proxy_port)
        return s

    engine = create_engine(url, creator=_socks_creator, **engine_kwargs)
    logger.info(f"[代理] 创建 SOCKS5 连接池: {proxy_host}:{proxy_port}")
    return engine, True


def setup_proxy_for_ds(ds, timeout: int = 60) -> tuple:
    """
    [已弃用] 旧版 proxy 设置函数，返回 (None, use_socks)。
    新版使用 create_socks_engine()。
    """
    use_socks = _get_proxy_info(ds) is not None
    return None, use_socks


def restore_socket(original_socket):
    """
    [已弃用] 空操作 — 保留用于测试兼容。
    新版无需恢复 socket。
    """
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
    if proxy_info:
        logger.info(f"[查询] 使用 SOCKS5 代理: {proxy_info['host']}:{proxy_info['port']}")
        engine = create_engine(
            conn_url,
            creator=_build_socks_creator(proxy_info['host'], proxy_info['port'], timeout=300),
            poolclass=QueuePool, pool_size=2, max_overflow=4,
        )
    else:
        engine = create_engine(conn_url, poolclass=QueuePool, pool_size=2, max_overflow=4,
                               connect_args=connect_args)

    max_retries = 2
    try:
        for attempt in range(max_retries):
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(sql))
                    columns = list(result.keys())
                    rows = []
                    BATCH_SIZE = 100000
                    while True:
                        batch = result.fetchmany(BATCH_SIZE)
                        if not batch:
                            break
                        rows.extend([list(row) for row in batch])
                    return rows, columns
            except OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise ValueError(f"查询执行失败: {e}")
    finally:
        engine.dispose()
