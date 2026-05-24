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

_original_global_socket = _socket.socket  # 保存系统全局 socket 原始引用


def _apply_socks_proxy(proxy_host: str, proxy_port: int, timeout: int = 60):
    """全局替换 socket 为 SOCKS5 代理 socket"""
    if not _HAS_SOCKS:
        raise RuntimeError("SOCKS5 代理需要 PySocks 库: pip install PySocks")
    _socks.set_default_proxy(_socks.SOCKS5, proxy_host, proxy_port)
    _socket.socket = _socks.socksocket
    _socket.setdefaulttimeout(timeout)


def _restore_socket():
    """恢复原始 socket"""
    global _original_global_socket
    _socket.socket = _original_global_socket
    try:
        _socks.set_default_proxy()
    except Exception:
        pass


@contextmanager
def socks_proxy_context(ds, db_session=None, timeout: int = 60):
    """
    基于数据源配置的 SOCKS5 代理上下文管理器。

    入口打 socket 补丁 → engine 连接走代理 → 退出恢复原始 socket。
    所有外部数据源连接都应该使用此 context manager。

    Args:
        ds: 数据源对象（需有 use_proxy / proxy_server_id 属性）
        db_session: 可选现有 DB session，为 None 时临时创建
        timeout: socket 超时秒数

    Yields: (use_socks: bool) — 调用方可判断是否走了代理
    """
    use_socks = False
    if getattr(ds, 'use_proxy', False) and getattr(ds, 'proxy_server_id', None):
        try:
            from app.models.proxy_server import ProxyServer
            # 查询代理配置
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
                _apply_socks_proxy(proxy.host, proxy.port, timeout)
                use_socks = True
                logger.debug(f"[代理] SOCKS5 {proxy.host}:{proxy.port} 已应用")
        except Exception as e:
            logger.warning(f"[代理] 设置 SOCKS5 代理失败: {e}")

    try:
        yield use_socks
    finally:
        if use_socks:
            _restore_socket()


def setup_socks(ds, db_session=None, timeout: int = 60):
    """
    设置 SOCKS5 代理并返回 cleanup 函数。

    适用于控制流复杂的场景（try/except/finally 嵌套），
    调用方在 finally 中调用返回的 cleanup 即可。

    Args:
        ds: 数据源对象
        db_session: 可选 DB session
        timeout: socket 超时

    Returns:
        cleanup: 调用以恢复 socket 的可调用对象（无操作时返回空函数
    """
    try:
        ctx = socks_proxy_context(ds, db_session, timeout)
        use_socks = ctx.__enter__()
        if use_socks:
            return lambda: ctx.__exit__(None, None, None)
        else:
            ctx.__exit__(None, None, None)
            return lambda: None
    except Exception:
        return lambda: None


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
    """(保留兼容) 旧的函数式接口，返回 (original_socket, use_socks)"""
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


def restore_socket(original_socket):
    """(保留兼容) 旧的恢复函数"""
    _socket.socket = original_socket
    try:
        _socks.set_default_proxy()
    except Exception:
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
        conn_url = f"postgresql://{ds.username}:***@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type in ("MYSQL", "DORIS"):
        conn_url = f"mysql+pymysql://{ds.username}:***@{ds.host}:{ds.port}/{ds.database}"
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

    # 使用统一上下文管理器处理 SOCKS5 代理
    with socks_proxy_context(ds, timeout=300) as use_socks:
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
