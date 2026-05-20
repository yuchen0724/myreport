"""数据库连接池管理器 - 复用跨请求的连接池"""

import logging
from threading import Lock
from typing import Dict, Optional
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """全局连接池管理器，按数据源 ID 缓存 engine"""
    
    _instance = None
    _lock = Lock()
    _engines: Dict[int, "CachableEngine"] = {}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_engine(self, ds_id: int, ds_type: str, host: str, port: int, database: str, 
                   username: str, password: str, use_proxy: bool = False, proxy_server_id: int = None) -> "CachableEngine":
        """获取或创建数据源的连接池"""
        with self._lock:
            if ds_id in self._engines:
                cached = self._engines[ds_id]
                # 检查连接是否仍然有效（���单检查：pool 有可用连接）
                if cached.engine.pool.checkedin() >= 0:
                    cached.last_access = __import__("time").time()
                    return cached
                else:
                    # 连接池无效，清理
                    logger.warning(f"[连接池] 数据源 {ds_id} 的连接池失效，销毁重建")
                    try:
                        cached.engine.dispose()
                    except:
                        pass
                    del self._engines[ds_id]
            
            # 创建新连接池
            from urllib.parse import quote_plus
            encoded_password = quote_plus(password)
            
            if ds_type.upper() == "MYSQL" or ds_type.upper() == "DORIS":
                conn_url = f"mysql+pymysql://{username}:{encoded_password}@{host}:{port}/{database}"
            elif ds_type.upper() == "POSTGRESQL":
                conn_url = f"postgresql://{username}:{encoded_password}@{host}:{port}/{database}"
            else:
                raise ValueError(f"不支持的数据源类型: {ds_type}")
            
            connect_args = {}
            if ds_type.upper() != "POSTGRESQL":
                connect_args["connect_timeout"] = 30
                connect_args["read_timeout"] = 300
            
            engine = create_engine(
                conn_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args=connect_args,
            )
            
            self._engines[ds_id] = CachableEngine(engine)
            logger.info(f"[连接池] 为数据源 {ds_id} 创建新连接池")
            return self._engines[ds_id]
    
    def dispose_engine(self, ds_id: int):
        """手动释放指定数据源的连接池"""
        with self._lock:
            if ds_id in self._engines:
                try:
                    self._engines[ds_id].engine.dispose()
                except:
                    pass
                del self._engines[ds_id]
                logger.info(f"[连接池] 已释放数据源 {ds_id} 的连接池")
    
    def dispose_all(self):
        """释放所有连接池"""
        with self._lock:
            for ds_id, cached in self._engines.items():
                try:
                    cached.engine.dispose()
                except:
                    pass
            self._engines.clear()
            logger.info("[连接池] 已释放所有连接池")


class CachableEngine:
    """可缓存的引擎包装器"""
    
    def __init__(self, engine):
        self.engine = engine
        self.last_access = __import__("time").time()


# 全局实例
pool_manager = ConnectionPoolManager()