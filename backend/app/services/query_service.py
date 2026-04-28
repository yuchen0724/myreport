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
        if cost > 200:
            # TODO: 提示用户使用异步导出
            pass

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
                ).dict(),
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
        """执行查询并返回结果"""
        if ds.type == "MYSQL":
            import pymysql
            conn = pymysql.connect(
                host=ds.host,
                port=ds.port,
                user=ds.username,
                password=decrypt_password(ds.password_encrypted),
                database=ds.database,
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return {
                "columns": columns,
                "rows": [list(row.values()) for row in rows],
                "total": len(rows),
            }
        elif ds.type == "POSTGRESQL":
            import psycopg2
            conn = psycopg2.connect(
                host=ds.host,
                port=ds.port,
                user=ds.username,
                password=decrypt_password(ds.password_encrypted),
                database=ds.database
            )
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "total": len(rows),
            }
        elif ds.type == "DORIS":
            # Doris 使用 MySQL 协议
            import pymysql
            conn = pymysql.connect(
                host=ds.host,
                port=ds.port,
                user=ds.username,
                password=decrypt_password(ds.password_encrypted),
                database=ds.database,
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return {
                "columns": columns,
                "rows": [list(row.values()) for row in rows],
                "total": len(rows),
            }
        else:
            raise ValueError(f"不支持的数据源类型: {ds.type}")
