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
            return SQLQueryResponse(**cached_result["result"])

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

            response = SQLQueryResponse(
                columns=result["columns"],
                rows=result["rows"],
                total=result["total"],
                execution_time_ms=execution_time_ms,
            )

            # 缓存结果（5分钟）
            cache_service.set(optimized_sql, response.dict(), params=request.params, ttl=300)

            return response
        except Exception as e:
            raise ValueError(f"查询执行失败: {str(e)}")

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
