"""数据库全量查询执行器 - 直接返回行+列格式数据"""

import logging
import socket as _socket
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


def setup_proxy_for_ds(ds, timeout: int = 60) -> tuple:
    """
    根据数据源配置设置 SOCKS5 代理，返回 (original_socket, use_socks)
    调用方必须在 finally 中调用 restore_socket(original_socket) 恢复。
    如果数据源未配置代理或不是 SOCKS5，返回 (None, False)。
    """
    original_socket = None
    if not getattr(ds, "use_proxy", False) or not ds.proxy_server_id:
        return None, False
    try:
        from app.repositories.proxy_server_repository import ProxyServerRepository
        from app.core.database import SessionLocal
        proxy_db = SessionLocal()
        proxy_repo = ProxyServerRepository(proxy_db)
        proxy = proxy_repo.get_by_id(ds.proxy_server_id)
        proxy_db.close()
        if proxy and proxy.proxy_type.lower() == "socks5":
            original_socket = _socket.socket
            _apply_socks_proxy(proxy.host, proxy.port, timeout)
            return original_socket, True
    except Exception as e:
        import traceback
        logger.warning(f"[代理] setup_proxy_for_ds 异常: {type(e).__name__}: {e}")
        traceback.print_exc()
    return None, False


def _apply_socks_proxy(proxy_host: str, proxy_port: int, timeout: int = 60):
    """全局替换 socket 为 SOCKS5 代理 socket，设置超时避免无限挂死"""
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")
    _socks.set_default_proxy(_socks.SOCKS5, proxy_host, proxy_port)
    _socket.socket = _socks.socksocket
    _socket.setdefaulttimeout(timeout)


def restore_socket(original_socket):
    """恢复原始 socket"""
    _socket.socket = original_socket
    _socks.set_default_proxy()


def execute_query(ds, sql: str) -> tuple:
    """
    执行查询并返回 (rows, columns)
    支持数据源配置的 SOCKS5 代理（use_proxy + proxy_server_id）。
    """
    from sqlalchemy.exc import OperationalError
    import time

    password = decrypt_password(ds.password_encrypted)
    ds_type = ds.type.upper() if ds.type else "DORIS"

    if ds_type == "POSTGRESQL":
        conn_url = f"postgresql://{ds.username}:***@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type in ("MYSQL", "DORIS"):
        conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type == "HIVE":
        conn_url = f"hive://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    else:
        raise ValueError(f"不支持的数据源类型: {ds.type}")

    connect_args = {"connect_timeout": 30, "read_timeout": 600}

    # SOCKS5 代理（设置 5 分钟超时，避免无限挂死）
    original_socket, use_socks = setup_proxy_for_ds(ds, timeout=300)
    if use_socks:
        logger.info(f"[查询] 使用 SOCKS5 代理")

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
        if use_socks and original_socket is not None:
            restore_socket(original_socket)
