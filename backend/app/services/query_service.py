import time
import logging
import hashlib
import json
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.query_history_repository import QueryHistoryRepository
from app.schemas.query import SQLQueryRequest, SQLQueryResponse
from app.utils.sql_validator import SQLValidator
from app.core.security import decrypt_password
from app.services.cache_service import cache_service, full_cache_service
from app.utils.query_optimizer import QueryOptimizer

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.history_repo = QueryHistoryRepository(db)

    def execute_sql(self, request: SQLQueryRequest, user_id: int) -> SQLQueryResponse:
        """执行 SQL 查询"""
        # 验证 SQL 安全（SQLValidator.validate 是唯一校验入口）
        is_valid, message = SQLValidator.validate(request.sql)
        if not is_valid:
            raise ValueError(message)

        # 优化查询
        optimized_sql = QueryOptimizer.optimize_query(request.sql)

        # 估算查询成本
        cost = QueryOptimizer.estimate_query_cost(optimized_sql)
        suggest_async = cost > 200

        # 获取数据源
        ds = self.ds_repo.get_by_id(request.data_source_id)
        if not ds:
            raise ValueError("数据源不存在")

        # 调试日志
        logger.info(f"查询请求: page={request.page}, page_size={request.page_size}, sql={optimized_sql[:100]}")

        # 尝试从缓存获取（全量数据）
        # 直接使用 redis key，不依赖 cache_service 的 get 方法
        cache_key = f"query_full:{hashlib.md5((optimized_sql + json.dumps(request.params or {}, sort_keys=True)).encode()).hexdigest()}"
        
        try:
            if full_cache_service.redis_client:
                cached_data = full_cache_service.redis_client.get(cache_key)
                if cached_data:
                    cached = json.loads(cached_data)
                    result_data = cached.get("result", cached)
                    all_rows = result_data.get("rows", [])
                    total = len(all_rows)
                    page = request.page
                    page_size = request.page_size
                    start = (page - 1) * page_size
                    paginated_rows = all_rows[start:start + page_size]
                    logger.info(f"缓存命中，从全量数据切片: page={page}, start={start}, size={len(paginated_rows)}, total={total}")
                    return SQLQueryResponse(
                        columns=result_data.get("columns", []),
                        rows=paginated_rows,
                        total=total,
                        page=page,
                        page_size=page_size,
                        execution_time_ms=result_data.get("execution_time_ms", 0),
                        suggest_async=suggest_async,
                    )
        except Exception as e:
            logger.warning(f"缓存读取失败: {e}")

        # 执行查询 - 首次查询获取全量数据
        start_time = time.time()
        try:
            # 第一页且请求的 page_size 较小（意味着用户在看第一页），查询全量数据
            request_page_size = 999999 if request.page == 1 else request.page_size
            
            result = self._execute_query(ds, optimized_sql, request.params, 1, request_page_size)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # 保存查询历史
            self.history_repo.create({
                "user_id": user_id,
                "data_source_id": request.data_source_id,
                "query_type": "SQL",
                "query_text": optimized_sql,
                "execution_time_ms": execution_time_ms,
                "row_count": result["total"],
            })

            # 分页 - 从全量数据切片
            all_rows = result["rows"]
            total = result["total"]
            page = request.page
            page_size = request.page_size
            start = (page - 1) * page_size
            paginated_rows = all_rows[start:start + page_size]

            response = SQLQueryResponse(
                columns=result["columns"],
                rows=paginated_rows,
                total=total,
                page=page,
                page_size=page_size,
                execution_time_ms=execution_time_ms,
                suggest_async=suggest_async,
            )

            # 缓存全量结果（5分钟）- 只有第一页查询才缓存全量
            if request.page == 1:
                try:
                    if full_cache_service.redis_client:
                        cache_key_write = f"query_full:{hashlib.md5((optimized_sql + json.dumps(request.params or {}, sort_keys=True)).encode()).hexdigest()}"
                        cached_data = {
                            "result": SQLQueryResponse(
                                columns=result["columns"],
                                rows=all_rows,
                                total=total,
                                page=1,
                                page_size=999999,
                                execution_time_ms=execution_time_ms,
                                suggest_async=suggest_async,
                            ).model_dump(),
                            "cached_at": datetime.now().isoformat(),
                            "ttl": 300
                        }
                        full_cache_service.redis_client.setex(cache_key_write, 300, json.dumps(cached_data))
                        logger.info(f"缓存全量数据: key={cache_key_write}, total={total}")
                except Exception as e:
                    logger.warning(f"缓存写入失败: {e}")

            return response
        except Exception as e:
            error_msg = str(e)
            if not error_msg:
                error_msg = f"{type(e).__name__}"
            raise ValueError(f"查询执行失败: {error_msg}")

    def _execute_query(self, ds, sql: str, params: Optional[dict], page: int = 1, page_size: int = 100) -> dict:
        """执行查询并返回结果（带连接池和超时）"""
        import pymysql
        import psycopg2
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import QueuePool
        
        # 查询超时时间（秒）
        QUERY_TIMEOUT = 30
        
        # 构建连接 URL
        if ds.type == "MYSQL":
            conn_url = f"mysql+pymysql://{ds.username}:{decrypt_password(ds.password_encrypted)}@{ds.host}:{ds.port}/{ds.database}"
            engine = create_engine(
                conn_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        elif ds.type == "POSTGRESQL":
            conn_url = f"postgresql://{ds.username}:{decrypt_password(ds.password_encrypted)}@{ds.host}:{ds.port}/{ds.database}"
            engine = create_engine(
                conn_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        elif ds.type == "DORIS":
            # Doris 使用 MySQL 协议
            conn_url = f"mysql+pymysql://{ds.username}:{decrypt_password(ds.password_encrypted)}@{ds.host}:{ds.port}/{ds.database}"
            engine = create_engine(
                conn_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        else:
            raise ValueError(f"不支持的数据源类型: {ds.type}")
        
        # 使用连接池执行查询（带超时和重试）
        import re
        from sqlalchemy.exc import OperationalError
        
        max_retries = 3
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                with engine.connect() as conn:
                    # 根据数据库类型设置查询超时
                    if ds.type == "MYSQL" or ds.type == "DORIS":
                        conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {QUERY_TIMEOUT*1000}"))
                    elif ds.type == "POSTGRESQL":
                        conn.execute(text(f"SET SESSION STATEMENT_TIMEOUT = '{QUERY_TIMEOUT}s'"))
                    
                    # 将 ${xxx} 格式转换为 :xxx 格式（SQLAlchemy 参数绑定格式）
                    converted_sql = re.sub(r'\$\{(\w+)\}', r':\1', sql)
                    
                    # 添加分页 LIMIT 和 OFFSET（仅当 page_size < 999999 时添加）
                    if page_size < 999999:
                        offset = (page - 1) * page_size
                        converted_sql = converted_sql.rstrip(';').strip()
                        if re.search(r'\bLIMIT\b', converted_sql, re.IGNORECASE):
                            converted_sql = re.sub(r'\bLIMIT\s+\d+', f'LIMIT {page_size}', converted_sql, flags=re.IGNORECASE)
                            if re.search(r'\bOFFSET\b', converted_sql, re.IGNORECASE):
                                converted_sql = re.sub(r'\bOFFSET\s+\d+', f'OFFSET {offset}', converted_sql, flags=re.IGNORECASE)
                            else:
                                converted_sql += f' OFFSET {offset}'
                        else:
                            converted_sql += f' LIMIT {page_size} OFFSET {offset}'
                    
                    logger.info(f"执行查询: page={page}, page_size={page_size}")
                    
                    # 执行查询，支持参数绑定（缺少参数时设为空字符串）
                    if params:
                        # 对于缺失的参数，使用空字符串替代（避免 SQLAlchemy 报错）
                        all_placeholders = set(re.findall(r':(\w+)', converted_sql))
                        filtered_params = {}
                        for placeholder in all_placeholders:
                            if placeholder in params and params[placeholder] is not None and params[placeholder] != '':
                                filtered_params[placeholder] = params[placeholder]
                            else:
                                # 参数缺失时设置为空字符串
                                filtered_params[placeholder] = ''
                        result = conn.execute(text(converted_sql), filtered_params)
                    else:
                        result = conn.execute(text(converted_sql))
                    
                    columns = list(result.keys())
                    rows = [list(row) for row in result.fetchall()]
                
                engine.dispose()
                
                # 获取总数
                # 如果返回行数等于 page_size，说明可能还有更多数据
                total = len(rows)
                has_more = len(rows) >= page_size
                
                return {
                    "columns": columns,
                    "rows": rows,
                    "total": total,
                    "has_more": has_more,  # 告知前端是否还有更多数据
                }
                
            except OperationalError as e:
                error_msg = str(e)
                if "fail to send batch" in error_msg or "network" in error_msg.lower():
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (attempt + 1))  # 递增等待时间
                        continue
                raise ValueError(f"查询执行失败: {error_msg}")
        
        # 不应该到达这里
        raise ValueError("查询重试失败")
