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
from app.utils.metrics import metrics_collector
from app.utils.query_optimizer import QueryOptimizer

from app.utils.db_executor import socks_proxy_context

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.history_repo = QueryHistoryRepository(db)

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
        is_valid, message = SQLValidator.validate(request.sql)
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
        import pymysql
        import psycopg2
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import QueuePool
        
        # 记录查询开始时间
        start_time = time_module.time()
        
        # 查询超时时间（秒）
        QUERY_TIMEOUT = 30
        
        # 构建连接 URL（统一使用 ds_type）
        from urllib.parse import quote_plus
        ds_type = ds.type.upper() if ds.type else ""
        password = decrypt_password(ds.password_encrypted)
        encoded_password = quote_plus(password)

        with socks_proxy_context(ds, db_session=self.db, timeout=60):
            connect_args = {}
        
            if ds_type == "MYSQL":
                conn_url = f"mysql+pymysql://{ds.username}:{encoded_password}@{ds.host}:{ds.port}/{ds.database}"
                engine = create_engine(
                    conn_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args=connect_args,
                )
            elif ds_type == "POSTGRESQL":
                conn_url = f"postgresql://{ds.username}:{encoded_password}@{ds.host}:{ds.port}/{ds.database}"
                engine = create_engine(
                    conn_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                )
            elif ds_type == "DORIS":
                # Doris 使用 MySQL 协议
                conn_url = f"mysql+pymysql://{ds.username}:{encoded_password}@{ds.host}:{ds.port}/{ds.database}"
                engine = create_engine(
                    conn_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args=connect_args,
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
                        if ds_type == "MYSQL" or ds_type == "DORIS":
                            conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {QUERY_TIMEOUT*1000}"))
                        elif ds_type == "POSTGRESQL":
                            conn.execute(text(f"SET SESSION STATEMENT_TIMEOUT = '{QUERY_TIMEOUT}s'"))
                        
                        # 将 ${xxx} 格式转换为 :xxx 格式（SQLAlchemy 参数绑定格式）
                        # 使用原生字符串避免 % 被解释为格式化符
                        converted_sql = sql.replace('${', ':').replace('}', '')
                        
                        # 添加分页 LIMIT 和 OFFSET（仅当 page_size < 999999 时添加）
                        if page_size < 999999:
                            offset = (page - 1) * page_size
                            converted_sql = converted_sql.rstrip(';').strip()
                            # 去掉任何现有的 LIMIT 和 OFFSET
                            converted_sql = re.sub(r';?\s*LIMIT\s+\d+\s*OFFSET\s+\d+\s*$', '', converted_sql, flags=re.IGNORECASE)
                            converted_sql = re.sub(r';?\s*LIMIT\s+\d+\s*$', '', converted_sql, flags=re.IGNORECASE)
                            
                            # 【新增】NL2SQL 查询直接使用普通分页，跳过所有深度分页检查
                            if skip_deep_pagination_check:
                                # 直接添加 LIMIT OFFSET，不做其他处理
                                converted_sql = f"{converted_sql} LIMIT {page_size} OFFSET {offset}"
                                logger.info("NL2SQL查询：跳过深度分页检查，使用普通分页 LIMIT OFFSET")
                                
                                # 直接执行查询，跳过后续的分页逻辑
                                logger.info(f"执行查询: page={page}, page_size={page_size}")
                                has_placeholders = bool(re.search(r':(\w+)', converted_sql))
                                
                                if has_placeholders and params:
                                    all_placeholders = set(re.findall(r':(\w+)', converted_sql))
                                    filtered_params = {}
                                    for placeholder in all_placeholders:
                                        if placeholder in params and params[placeholder] is not None and params[placeholder] != '':
                                            filtered_params[placeholder] = params[placeholder]
                                    result = conn.execute(text(converted_sql), filtered_params)
                                else:
                                    result = conn.execute(text(converted_sql))
                                
                                # 获取列名
                                columns = [col[0] for col in result.cursor.description] if result.cursor.description else []
                                rows = [list(row) for row in result.fetchall()]
                                
                                return {
                                    "columns": columns,
                                    "rows": rows,
                                    "total": len(rows),
                                    "has_more": False,
                                    "order_cols": [],
                                }
                            
                            # 提取 ORDER BY 子句，用于后续分页
                            order_by_match = re.search(r'\bORDER\s+BY\s+(.+?)(?:\s+LIMIT|\s+OFFSET|\s*$)', converted_sql, re.IGNORECASE)
                            
                            # 如果没有 ORDER BY，根据 skip_deep_pagination_check 决定处理方式
                            if not order_by_match:
                                if skip_deep_pagination_check:
                                    # NL2SQL 查询：直接使用普通分页
                                    converted_sql = f"{converted_sql} LIMIT {page_size} OFFSET {offset}"
                                    logger.info("NL2SQL查询：无ORDER BY，使用普通分页 LIMIT OFFSET")
                                else:
                                    # 模板查询：需要 ORDER BY
                                    raise ValueError("深度分页需要明确的 ORDER BY，请在 SQL 中添加 ORDER BY 子句")
                            
                            if order_by_match:
                                order_by_clause = order_by_match.group(1)
                                order_cols = [col.strip().split()[0] for col in order_by_clause.split(',')]
                                
                                # 清理 SQL 中的 ORDER BY（后续会重新添加）
                                converted_sql = re.sub(r'\s+ORDER\s+BY\s+.+?(?=\s*LIMIT|\s*$)', '', converted_sql, flags=re.IGNORECASE).strip()
                            else:
                                order_cols = []
                            
                            # 构建游标分页 SQL
                            cursor = cursor  # 直接使用参数传入的 cursor
                            cursor_where = ""
                            cursor_key = None
                            query_params = {}  # 初始化参数化查询参数
                            
                            if cursor:
                                # 游标分页：WHERE (col1, col2) > (val1, val2)
                                # 安全修复：列名必须来自 ORDER BY 白名单，值使用参数化查询
                                cursor_parts = [c.strip() for c in cursor.split(',')]
                                where_parts = []
                                query_params = {}  # 参数化查询参数
                                for i, col in enumerate(order_cols):
                                    if i < len(cursor_parts):
                                        val = cursor_parts[i]
                                        param_name = f"cursor_{i}"
                                        # 检查是否为有效列名（防御）
                                        if not col.isidentifier():
                                            raise ValueError(f"无效的排序列名: {col}")
                                        # 根据值类型决定比较方式：数值无引号，字符���有引号
                                        if val and val.lstrip('-').replace('.', '', 1).isdigit():
                                            # 数值类型
                                            where_parts.append(f"{col} > :{param_name}")
                                            query_params[param_name] = float(val) if '.' in val else int(val)
                                        else:
                                            # 字符串类型，使用参数化查询
                                            where_parts.append(f"{col} > :{param_name}")
                                            query_params[param_name] = val
                                if where_parts:
                                    cursor_where = " WHERE " + " AND ".join(where_parts)
                                
                                # 生成缓存 key
                                sql_hash = hashlib.md5((sql + str(page_size)).encode()).hexdigest()[:8]
                                cursor_key = f"cursor:{sql_hash}:{cursor}"
                                
                                logger.info(f"游标分页: cursor={cursor}, key={cursor_key}")
                            
                            # 构建最终 SQL
                            if cursor_where:
                                # 游标分页（性能最优）
                                converted_sql = f"SELECT * FROM ({converted_sql}) as t {cursor_where} ORDER BY {order_by_clause} LIMIT {page_size}"
                            elif offset > 1000:
                                # 深度分页优化：OFFSET > 1000 时使用窗口函数
                                converted_sql = f"SELECT * FROM (SELECT ROW_NUMBER() OVER (ORDER BY {order_by_clause}) as _rn, t.* FROM ({converted_sql}) as t) as t_paged WHERE _rn > {offset} AND _rn <= {offset + page_size}"
                                logger.info(f"深度分页优化: offset={offset}, 使用窗口函数")
                            else:
                                # 普通分页
                                converted_sql += f' ORDER BY {order_by_clause} LIMIT {page_size} OFFSET {offset}'
                        
                        logger.info(f"执行查询: page={page}, page_size={page_size}")
                        
                        # 执行查询
                        # 检查 SQL 中是否还有占位符
                        has_placeholders = bool(re.search(r':(\w+)', converted_sql))
                        
                        if has_placeholders and params:
                            # 绑定参数
                            all_placeholders = set(re.findall(r':(\w+)', converted_sql))
                            filtered_params = {}
                            for placeholder in all_placeholders:
                                if placeholder in params and params[placeholder] is not None and params[placeholder] != '':
                                    filtered_params[placeholder] = params[placeholder]
                                else:
                                    filtered_params[placeholder] = ''
                            # 合并游标参数（如果有）
                            if 'query_params' in dir() and query_params:
                                filtered_params.update(query_params)
                            result = conn.execute(text(converted_sql), filtered_params)
                        elif has_placeholders:
                            # SQL 有占位符但没传参数，使用空字符串
                            all_placeholders = set(re.findall(r':(\w+)', converted_sql))
                            filtered_params = {p: '' for p in all_placeholders}
                            result = conn.execute(text(converted_sql), filtered_params)
                        else:
                            # 无占位符，直接执行
                            result = conn.execute(text(converted_sql))
                        
                        columns = list(result.keys())
                        rows = [list(row) for row in result.fetchall()]
                    
                    # 获取真实总数
                    # 如果 page_size >= 999999（全量查询），total 就是实际返回行数
                    # 否则需要执行 COUNT(*) 获取真实总数
                    if page_size < 999999:
                        try:
                            # 使用原始 SQL（未添加分页的）来构造 COUNT 查询
                            # 先将参数占位符转换，但不添加 LIMIT
                            count_base_sql = re.sub(r'\$\{(\w+)\}', r':\1', sql)
                            # 去掉任何现有的 LIMIT 和 ORDER BY（COUNT 时不需要）
                            count_base_sql = count_base_sql.strip()
                            count_base_sql = re.sub(r';?\s*LIMIT\s+\d+\s*OFFSET\s+\d+\s*$', '', count_base_sql, flags=re.IGNORECASE)
                            count_base_sql = re.sub(r';?\s*LIMIT\s+\d+\s*$', '', count_base_sql, flags=re.IGNORECASE)
                            count_sql = f"SELECT COUNT(*) as cnt FROM ({count_base_sql}) as _subquery"
                            
                            with engine.connect() as conn2:
                                # COUNT 查询使用较短超时
                                count_timeout = max(10, QUERY_TIMEOUT // 2)
                                if ds_type == "MYSQL" or ds_type == "DORIS":
                                    conn2.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {count_timeout*1000}"))
                                elif ds_type == "POSTGRESQL":
                                    conn2.execute(text(f"SET SESSION STATEMENT_TIMEOUT = '{count_timeout}s'"))
                                
                                # 使用原始参数
                                exec_params = {}
                                if params:
                                    all_placeholders = set(re.findall(r':(\w+)', count_base_sql))
                                    for placeholder in all_placeholders:
                                        if placeholder in params and params[placeholder] is not None and params[placeholder] != '':
                                            exec_params[placeholder] = params[placeholder]
                                        else:
                                            exec_params[placeholder] = ''
                                
                                count_result = conn2.execute(text(count_sql), exec_params)
                                total = count_result.scalar() or 0
                                logger.info(f"COUNT 查询结果: total={total}")
                        except Exception as e:
                            logger.warning(f"COUNT 查询失败，回退到行数: {e}")
                            total = len(rows)
                    else:
                        total = len(rows)
                    
                    # 在所有查询完成后释放连接池
                    engine.dispose()
                    
                    has_more = len(rows) >= page_size and total > (page - 1) * page_size + len(rows)
                    
                    return {
                        "columns": columns,
                        "rows": rows,
                        "total": total,
                        "has_more": has_more,
                        "order_cols": order_cols,
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
