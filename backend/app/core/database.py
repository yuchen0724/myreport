from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import get_settings

settings = get_settings()

# SQLite 需要 check_same_thread=False 以支持多线程访问
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# 根据数据库类型配置连接池
pool_config = {
    "poolclass": QueuePool,
    "pool_size": 10,              # 基础连接数
    "max_overflow": 20,           # 最大溢出连接数
    "pool_pre_ping": True,        # 使用连接前先测试连接有效性
    "pool_recycle": 1800,         # 30分钟回收连接
    "pool_timeout": 30,           # 获取连接超时时间
    "echo": False,                # 是否打印 SQL（开发环境设为 True）
}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **pool_config
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
