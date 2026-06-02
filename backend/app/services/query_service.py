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
from app.utils.sql_normalizer import strip_trailing_semicolon
from app.core.security import decrypt_password  # noqa: F401 - kept for legacy patch points
from app.services.cache_service import cache_service, full_cache_service
from app.utils.metrics import metrics_collector
from app.utils.query_optimizer import QueryOptimizer
from app.services.datasource_engine_factory import DataSourceEngineFactory
from app.services.query_executor import QueryExecutor
from app.services.sql_pagination import SqlPaginator

from app.utils.db_executor import _get_proxy_info

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.history_repo = QueryHistoryRepository(db)
        self.engine_factory = DataSourceEngineFactory()
        self.sql_paginator = SqlPaginator()
        self.query_executor = QueryExecutor()

    def _make_cache_key(self, sql: str, params: Optional[dict], page: int, page_size: int, cursor: Optional[str], skip_deep_pagination_check: bool) -> str:
        """生成带分页参数的缓存键"""
        cache_data = {
            "sql": sql,
            "params": params or {},
            "page": page,
            "page_size": page_size,
            "cursor": cursor,
            "skip_deep_pagination_check": skip_deep_pagination_check,
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return f"query_result:{hashlib.md5(cache_str.encode()).hexdigest()}"

    def execute_sql(self, request: SQLQueryRequest, user_id: int) -> SQLQueryResponse:
        """执行 SQL 查询"""
        # 验证 SQL 安全（SQLValidator.validate 是唯一校验入口）
        sql = strip_trailing_semicolon(request.sql)
        is_valid, message = SQLValidator.validate(sql)
        if not is_valid:
            raise ValueError(message)

        # 优化查��
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

        # 从数据源类型推断缓存 TTL
        ds_type = ds.type.upper() if ds.type else ""
        ttl = cache_service.DEFAULT_TTL_BY_SOURCE.get(ds_type, 300)

        cursor_val = getattr(request, 'cursor', None)
        skip_val = getattr(request, 'skip_deep_pagination_check', False)

        # 检查缓存
        cache_key = self._make_cache_key(optimized_sql, request.params, request.page, request.page_size, cursor_val, skip_val)
        cached = cache_service.redis_client.get(cache_key) if cache_service.redis_client else None
        if cached:
            cached_data = json.loads(cached)
            logger.info(f"缓存命中: key={cache_key[:40]}...")
            # 从缓存数据重建 SQLQueryResponse，标记 cache_hit=True
            resp_data = cached_data["response"]
            resp_data["cache_hit"] = True
            return SQLQueryResponse(**resp_data)

        # 简化处理：不再使用全量缓存策略，每次查询都获取当前页数据 + COUNT 总数
        # 这样可以避免缓存不一致问题，同时保证分页正确
        
        # 执行查询 - 使用用户请求的实际 page_size
        start_time = time.time()
        try:
            # 直接使用用户请求的 page_size，不再获取全量
            result = self._execute_query(ds, optimized_sql, request.params, request.page, request.page_size, getattr(request, 'cursor', None), skip_deep_pagination_check=getattr(request, 'skip_deep_pagination_check', False))
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

            # 分页 - 数据已经是当前页的结果，total 是通过 COUNT 获取的真实总数
            rows = result["rows"]
            total = result["total"]
            page = request.page
            page_size = request.page_size
            
            # 游标分页：计算当前页游标和下一页游标
            cursor = getattr(request, 'cursor', None)
            next_cursor = None
            order_cols = result.get("order_cols", [])
            
            if rows and order_cols:
                # 从最后一行提取排序字段值作为 next_cursor
                last_row = rows[-1]
                cursor_parts = []
                for col in order_cols:
                    # 找到该列在 column 列表中的索引
                    col_idx = result["columns"].index(col) if col in result["columns"] else None
                    if col_idx is not None and col_idx < len(last_row):
                        val = last_row[col_idx]
                        cursor_parts.append(str(val) if val is not None else '')
                if cursor_parts:
                    next_cursor = ','.join(cursor_parts)
            
            # 计算实际 page（用于游标分页时可能不准确）
            if cursor and not page:
                # 游标模式下无法准确知道 pageNum
                page = 1
            
            response = SQLQueryResponse(
                columns=result["columns"],
                rows=rows,
                total=total,
                page=page,
                page_size=page_size,
                execution_time_ms=execution_time_ms,
                suggest_async=suggest_async,
                cursor=cursor,
                next_cursor=next_cursor,
            )

            # 写入缓存
            if cache_service.redis_client:
                try:
                    cache_service.redis_client.setex(
                        cache_key,
                        ttl,
                        json.dumps({"response": response.model_dump()}, default=str)
                    )
                    logger.info(f"缓存写入: key={cache_key[:40]}..., ttl={ttl}s")
                except Exception as e:
                    logger.warning(f"缓存写入失败: {e}")

            # 慢查询记录
            if execution_time_ms >= metrics_collector.slow_query_threshold_ms:
                metrics_collector.record_slow_query(
                    sql=optimized_sql,
                    data_source_id=request.data_source_id,
                    data_source_name=ds.name or ds.type or str(ds.id),
                    execution_time_ms=execution_time_ms,
                    row_count=total,
                    user_id=user_id,
                )

            return response
        except Exception as e:
            error_msg = str(e)
            if not error_msg:
                error_msg = f"{type(e).__name__}"
            raise ValueError(f"查询执行失败: {error_msg}")

    def _execute_query(self, ds, sql: str, params: Optional[dict], page: int = 1, page_size: int = 100, cursor: Optional[str] = None, skip_deep_pagination_check: bool = False) -> dict:
        """执行查询并返回结果（带连接池和超时）"""
        import time as time_module
        
        ds_type = ds.type.upper() if ds.type else ""

        proxy_info = _get_proxy_info(ds, db_session=self.db)
        if proxy_info:
            engine = self.engine_factory.create_engine_with_proxy(
                ds, proxy_info["host"], proxy_info["port"]
            )
        else:
            engine = self.engine_factory.create_engine(ds)
            
            # 使用连接池执行查询（带超时和重试）
            from sqlalchemy.exc import OperationalError
            
            max_retries = 3
            retry_delay = 1  # 秒
            
            try:
                for attempt in range(max_retries):
                    try:
                        with engine.connect() as conn:
                            self.query_executor.apply_timeout(conn, ds_type)

                            paginated_sql = self.sql_paginator.build(
                                sql=sql,
                                page=page,
                                page_size=page_size,
                                cursor=cursor,
                                skip_deep_pagination_check=skip_deep_pagination_check,
                            )
                            if paginated_sql.is_nl2sql_skip:
                                logger.info("NL2SQL查询：跳过深度分页检查，使用普通分页 LIMIT OFFSET")
                            elif paginated_sql.cursor_params:
                                logger.info(f"游标分页: cursor={cursor}")
                            elif page_size < 999999 and (page - 1) * page_size > 1000:
                                logger.info(f"深度分页优化: offset={(page - 1) * page_size}, 使用窗口函数")
                            
                            logger.info(f"执行查询: page={page}, page_size={page_size}")

                            query_params = None
                            if self.sql_paginator.has_placeholders(paginated_sql.query_sql):
                                query_params = self.sql_paginator.filter_params(paginated_sql.query_sql, params)
                                query_params.update(paginated_sql.cursor_params)
                            columns, rows = self.query_executor.execute_rows(
                                conn,
                                paginated_sql.query_sql,
                                query_params,
                            )

                        # 获取真实总数
                        # 如果 page_size >= 999999（全量查询），total 就是实际返回行数
                        # 否则需要执行 COUNT(*) 获取真实总数
                        if paginated_sql.should_count:
                            try:
                                count_sql, count_base_sql = self.sql_paginator.build_count_sql(sql)
                                
                                with engine.connect() as conn2:
                                    self.query_executor.apply_timeout(
                                        conn2,
                                        ds_type,
                                        self.query_executor.count_timeout_seconds,
                                    )
                                    exec_params = self.sql_paginator.filter_params(count_base_sql, params)
                                    total = self.query_executor.execute_scalar(conn2, count_sql, exec_params) or 0
                                    logger.info(f"COUNT 查询结果: total={total}")
                            except Exception as e:
                                logger.warning(f"COUNT 查询失败，回退到行数: {e}")
                                total = len(rows)
                        else:
                            total = len(rows)

                        has_more = len(rows) >= page_size and total > (page - 1) * page_size + len(rows)

                        return {
                            "columns": columns,
                            "rows": rows,
                            "total": total,
                            "has_more": has_more,
                            "order_cols": paginated_sql.order_cols,
                        }
                    except OperationalError as e:
                        error_msg = str(e)
                        if "fail to send batch" in error_msg or "network" in error_msg.lower():
                            if attempt < max_retries - 1:
                                time_module.sleep(retry_delay * (attempt + 1))  # 递增等待时间
                                continue
                        raise ValueError(f"查询执行失败: {error_msg}")

                # 不应该到达这里
                raise ValueError("查询重试失败")
            finally:
                engine.dispose()
