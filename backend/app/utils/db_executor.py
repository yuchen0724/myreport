"""数据库全量查询执行器 - 直接返回行+列格式数据"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from app.core.security import decrypt_password

logger = logging.getLogger(__name__)


def execute_query(ds, sql: str) -> tuple:
    """
    执行查询并返回 (rows, columns)
    供预测任务拉取全量训练数据使用。
    """
    from sqlalchemy.exc import OperationalError
    import time

    password = decrypt_password(ds.password_encrypted)
    ds_type = ds.type.upper() if ds.type else "DORIS"

    if ds_type == "POSTGRESQL":
        conn_url = f"postgresql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type in ("MYSQL", "DORIS"):
        conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type == "HIVE":
        conn_url = f"hive://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    else:
        raise ValueError(f"不支持的数据源类型: {ds.type}")

    engine = create_engine(conn_url, poolclass=QueuePool, pool_size=2, max_overflow=4,
                           connect_args={"connect_timeout": 30, "read_timeout": 600})

    max_retries = 2
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = list(result.keys())
                # 分批拉取，避免 OOM
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
