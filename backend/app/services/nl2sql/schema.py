"""Schema retrieval — fetch table metadata from data sources via SQLAlchemy."""

import logging
from typing import Dict, List, Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.security import decrypt_password

logger = logging.getLogger(__name__)


class SchemaRetriever:
    """Retrieve database schema (tables, columns) from external data sources."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def fetch_schema(self, ds) -> Dict[str, List[Dict[str, Any]]]:
        """
        从数据源获取表结构。

        Returns: {表名: [列信息字典]} 格式的字典
        """
        password = decrypt_password(ds.password_encrypted)
        ds_type = ds.type.upper() if ds.type else ""

        # 代理 / 连接参数
        connect_args = {}
        proxy_info = self._resolve_proxy(ds, ds_type)
        if proxy_info and ds_type not in ("MYSQL", "DORIS"):
            raise ValueError("SOCKS5 代理当前仅支持 MySQL/Doris 数据源")

        conn_url = self._build_conn_url(ds_type, ds.username, password, ds.host, ds.port, ds.database)
        engine = self._create_engine(conn_url, connect_args, proxy_info, ds, password)

        tables_info = {}
        try:
            with engine.connect() as conn:
                if ds_type in ("MYSQL", "DORIS"):
                    tables_info = self._fetch_mysql_tables(conn, ds_type)
                elif ds_type == "POSTGRESQL":
                    tables_info = self._fetch_postgres_tables(conn)
            return tables_info
        finally:
            engine.dispose()

    # ── Internal helpers ────────────────────────────────────

    def _resolve_proxy(self, ds, ds_type: str):
        """Resolve SOCKS5 proxy configuration."""
        if not getattr(ds, 'use_proxy', False) or not getattr(ds, 'proxy_server_id', None):
            return None
        from app.utils.db_executor import _get_proxy_info
        return _get_proxy_info(ds, db_session=self.db)

    def _maybe_set_http_proxy(self, ds, ds_type: str):
        """Set HTTP_PROXY env vars for PostgreSQL HTTP proxy."""
        import os
        if not getattr(ds, 'use_proxy', False) or not getattr(ds, 'proxy_server_id', None):
            return None
        if ds_type != "POSTGRESQL":
            return None
        from app.models.proxy_server import ProxyServer
        if self.db:
            proxy = self.db.query(ProxyServer).filter(ProxyServer.id == ds.proxy_server_id).first()
        else:
            proxy = None
        if proxy and proxy.is_active and proxy.proxy_type == "http":
            old_http = os.environ.get('HTTP_PROXY')
            old_https = os.environ.get('HTTPS_PROXY')
            proxy_url = f"http://{proxy.host}:{proxy.port}"
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            return {"set": True, "old_http": old_http, "old_https": old_https}
        return None

    def _restore_env_proxy(self, old_http, old_https):
        import os
        if old_http is None:
            os.environ.pop('HTTP_PROXY', None)
        else:
            os.environ['HTTP_PROXY'] = old_http
        if old_https is None:
            os.environ.pop('HTTPS_PROXY', None)
        else:
            os.environ['HTTPS_PROXY'] = old_https

    def _build_conn_url(self, ds_type: str, username: str, password: str,
                         host: str, port: int, database: str) -> str:
        from urllib.parse import quote_plus
        pwd = quote_plus(password)
        if ds_type in ("MYSQL", "DORIS"):
            return f"mysql+pymysql://{username}:{pwd}@{host}:{port}/{database}"
        elif ds_type == "POSTGRESQL":
            return f"postgresql://{username}:{pwd}@{host}:{port}/{database}"
        raise ValueError(f"不支持的数据源类型: {ds_type}")

    def _create_engine(self, conn_url: str, connect_args: dict, proxy_info: Optional[dict], ds, password: str):
        if proxy_info:
            from app.utils.db_executor import build_pymysql_socks_creator
            creator = build_pymysql_socks_creator(
                proxy_host=proxy_info['host'], proxy_port=proxy_info['port'],
                host=ds.host, port=ds.port, username=ds.username,
                password=password, database=ds.database,
            )
            return create_engine(conn_url, pool_pre_ping=True, creator=creator)
        return create_engine(conn_url, pool_pre_ping=True, connect_args=connect_args)

    def _fetch_mysql_tables(self, conn, ds_type: str) -> Dict[str, List[Dict[str, Any]]]:
        tables_info: Dict[str, List[Dict[str, Any]]] = {}
        tables_result = conn.execute(text("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """))
        tables_with_schema = [(row[0], row[1]) for row in tables_result.fetchall()][:50]

        for db_name, table_name in tables_with_schema:
            try:
                desc_result = conn.execute(text(f"DESCRIBE `{db_name}`.`{table_name}`"))
                columns = []
                for row in desc_result.fetchall():
                    columns.append({
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2],
                        "key": row[3] if len(row) > 3 else "",
                        "default": str(row[4]) if len(row) > 4 and row[4] is not None else "",
                        "comment": row[5] if len(row) > 5 else ""
                    })
                tables_info[f"{db_name}.{table_name}"] = columns
            except Exception as e:
                logger.warning("获取表 %s.%s 结构失败: %s", db_name, table_name, e)
                continue
        return tables_info

    def _fetch_postgres_tables(self, conn) -> Dict[str, List[Dict[str, Any]]]:
        tables_info: Dict[str, List[Dict[str, Any]]] = {}
        tables_result = conn.execute(text("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """))
        tables_with_schema = [(row[0], row[1]) for row in tables_result.fetchall()][:50]

        for db_name, table_name in tables_with_schema:
            try:
                desc_result = conn.execute(text("""
                    SELECT
                        column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = :schema_name AND table_name = :table_name
                    ORDER BY ordinal_position
                """), {"schema_name": db_name, "table_name": table_name})
                columns = []
                for row in desc_result.fetchall():
                    columns.append({
                        "name": row[0], "type": row[1],
                        "nullable": row[2], "key": "",
                        "default": str(row[3]) if row[3] else "", "comment": ""
                    })
                tables_info[f"{db_name}.{table_name}"] = columns
            except Exception as e:
                logger.warning("获取表 %s.%s 结构失败: %s", db_name, table_name, e)
                continue
        return tables_info

    def build_schema_prompt(self, ds, data_source_id: int, question: str) -> str:
        """
        构建 schema 提示词。
        先尝试从缓存获取，再从数据源实时获取。
        """
        from app.utils.nl2sql_cache import get_nl2sql_cache
        from app.utils.nl2sql_rules import get_query_rules

        cache_key = f"schema:{data_source_id}"
        try:
            cache = get_nl2sql_cache()
            cached = cache.get(cache_key) if cache else None
        except Exception:
            cached = None

        if cached:
            logger.info("使用缓存的 Schema")
            return cached

        schema_dict = self._fetch_compact_schema(ds)
        if not schema_dict or not any(schema_dict.values()):
            logger.warning("获取到的 Schema 为空")
            return ""

        # 转成文本
        schema_lines = []
        for table_name, columns in schema_dict.items():
            col_strs = []
            for col in columns:
                col_str = f"  - {col['name']} ({col['type']})"
                if col.get('key') in ('PRI', 'UNI'):
                    col_str += " [KEY]"
                col_strs.append(col_str)
            schema_lines.append(f"表: {table_name}")
            schema_lines.extend(col_strs)
            schema_lines.append("")

        schema_text = "\n".join(schema_lines)

        try:
            cache = get_nl2sql_cache()
            if cache:
                from app.config import get_settings
                cache.set(cache_key, schema_text, ttl=getattr(get_settings(), 'nl2sql_cache_ttl', 3600))
        except Exception:
            pass

        return schema_text

    def _fetch_compact_schema(self, ds) -> Dict[str, List[Dict[str, Any]]]:
        """获取 schema 但不包含 comment（用于 prompt）。"""
        full = self.fetch_schema(ds)
        compact = {}
        for table_name, columns in full.items():
            compact[table_name] = [
                {k: v for k, v in col.items() if k != "comment"}
                for col in columns
            ]
        return compact
