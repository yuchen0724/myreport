import time
from sqlalchemy.orm import Session
from typing import Optional
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.query_history_repository import QueryHistoryRepository
from app.schemas.query import SQLQueryRequest, SQLQueryResponse
from app.utils.sql_validator import SQLValidator
from app.core.security import decrypt_password
from app.services.cache_service import cache_service
from app.utils.query_optimizer import QueryOptimizer


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

        # 尝试从缓存获取
        cached_result = cache_service.get(optimized_sql, request.params)
        if cached_result:
            cached = SQLQueryResponse(**cached_result["result"])
            # 从缓存全量结果中切片
            page = request.page
            page_size = request.page_size
            start = (page - 1) * page_size
            paginated_rows = cached.rows[start:start + page_size]
            return SQLQueryResponse(
                columns=cached.columns,
                rows=paginated_rows,
                total=cached.total,
                page=page,
                page_size=page_size,
                execution_time_ms=cached.execution_time_ms,
                suggest_async=suggest_async,
            )

        # 执行查询
        start_time = time.time()
        try:
            result = self._execute_query(ds, optimized_sql, request.params)
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

            # 分页
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

            # 缓存全量结果（5分钟），用 page=1&page_size=999999 作为缓存 key 后缀
            cache_service.set(
                optimized_sql,
                SQLQueryResponse(
                    columns=result["columns"],
                    rows=all_rows,
                    total=total,
                    page=1,
                    page_size=999999,
                    execution_time_ms=execution_time_ms,
                    suggest_async=suggest_async,
                ).model_dump(),
                params=request.params,
                ttl=300,
            )

            return response
        except Exception as e:
            error_msg = str(e)
            if not error_msg:
                error_msg = f"{type(e).__name__}"
            raise ValueError(f"查询执行失败: {error_msg}")

    def _execute_query(self, ds, sql: str, params: Optional[dict]) -> dict:
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
        
        # 使用连接池执行查询（带超时）
        import re
        
        with engine.connect() as conn:
            # 根据数据库类型设置查询超时
            if ds.type == "MYSQL" or ds.type == "DORIS":
                conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {QUERY_TIMEOUT*1000}"))
            elif ds.type == "POSTGRESQL":
                conn.execute(text(f"SET SESSION STATEMENT_TIMEOUT = '{QUERY_TIMEOUT}s'"))
            
            # 将 ${xxx} 格式转换为 :xxx 格式（SQLAlchemy 参数绑定格式）
            converted_sql = re.sub(r'\$\{(\w+)\}', r':\1', sql)
            
            # 执行查询，支持参数绑定（缺少参数时忽略）
            if params:
                # 过滤掉 None 和空字符串的参数
                filtered_params = {k: v for k, v in params.items() if v is not None and v != ''}
                result = conn.execute(text(converted_sql), filtered_params)
            else:
                result = conn.execute(text(converted_sql))
            
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
        
        engine.dispose()
        
        return {
            "columns": columns,
            "rows": rows,
            "total": len(rows),
        }
