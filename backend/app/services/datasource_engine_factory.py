"""Data source SQLAlchemy engine factory."""

from dataclasses import dataclass
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from app.core.security import decrypt_password


@dataclass(frozen=True)
class DataSourceEngineConfig:
    ds_type: str
    url: str
    connect_args: dict


class DataSourceEngineFactory:
    """Build SQLAlchemy engines for external data sources."""

    def __init__(self, pool_size: int = 5, max_overflow: int = 10, pool_recycle: int = 3600):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_recycle = pool_recycle

    def build_config(self, ds) -> DataSourceEngineConfig:
        ds_type = ds.type.upper() if ds.type else ""
        password = quote_plus(decrypt_password(ds.password_encrypted))

        if ds_type in ("MYSQL", "DORIS"):
            url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
            connect_args = {}
        elif ds_type == "POSTGRESQL":
            url = f"postgresql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
            connect_args = {}
        else:
            raise ValueError(f"不支持的数据源类型: {ds.type}")

        return DataSourceEngineConfig(
            ds_type=ds_type,
            url=url,
            connect_args=connect_args,
        )

    def create_engine(self, ds):
        config = self.build_config(ds)
        return self._build_engine(config, ds)

    def _build_engine(self, config, ds=None, creator=None):
        kwargs = {
            "poolclass": QueuePool,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_pre_ping": True,
            "pool_recycle": self.pool_recycle,
        }
        if creator is not None:
            kwargs["creator"] = creator
        elif config.connect_args:
            kwargs["connect_args"] = config.connect_args
        elif config.ds_type in ("MYSQL", "DORIS"):
            kwargs["connect_args"] = {}

        return create_engine(config.url, **kwargs)

    def create_engine_with_proxy(self, ds, proxy_host: str, proxy_port: int):
        """Create an engine using a per-connection SOCKS5 socket."""
        config = self.build_config(ds)
        if config.ds_type not in ("MYSQL", "DORIS"):
            raise ValueError("SOCKS5 代理当前仅支持 MySQL/Doris 数据源")

        from app.utils.db_executor import build_pymysql_socks_creator

        creator = build_pymysql_socks_creator(
            proxy_host=proxy_host,
            proxy_port=proxy_port,
            host=ds.host,
            port=ds.port,
            username=ds.username,
            password=decrypt_password(ds.password_encrypted),
            database=ds.database,
        )
        return self._build_engine(config, ds, creator=creator)
