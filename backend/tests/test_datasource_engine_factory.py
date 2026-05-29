from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.pool import QueuePool

from app.services.datasource_engine_factory import DataSourceEngineFactory


@pytest.fixture
def ds():
    data_source = MagicMock()
    data_source.type = "MYSQL"
    data_source.host = "db-host"
    data_source.port = 3306
    data_source.database = "reporting"
    data_source.username = "user"
    data_source.password_encrypted = "encrypted"
    return data_source


@patch("app.services.datasource_engine_factory.decrypt_password", return_value="p@ss word")
def test_build_mysql_config_encodes_password(mock_decrypt, ds):
    config = DataSourceEngineFactory().build_config(ds)

    assert config.ds_type == "MYSQL"
    assert config.url == "mysql+pymysql://user:p%40ss+word@db-host:3306/reporting"
    assert config.connect_args == {}


@patch("app.services.datasource_engine_factory.decrypt_password", return_value="secret")
def test_build_doris_config_uses_mysql_protocol(mock_decrypt, ds):
    ds.type = "DORIS"
    ds.port = 9030

    config = DataSourceEngineFactory().build_config(ds)

    assert config.ds_type == "DORIS"
    assert config.url == "mysql+pymysql://user:secret@db-host:9030/reporting"


@patch("app.services.datasource_engine_factory.decrypt_password", return_value="secret")
def test_build_postgresql_config(mock_decrypt, ds):
    ds.type = "POSTGRESQL"
    ds.port = 5432

    config = DataSourceEngineFactory().build_config(ds)

    assert config.ds_type == "POSTGRESQL"
    assert config.url == "postgresql://user:secret@db-host:5432/reporting"


@patch("app.services.datasource_engine_factory.decrypt_password", return_value="secret")
def test_unsupported_type_raises(mock_decrypt, ds):
    ds.type = "HIVE"

    with pytest.raises(ValueError, match="不支持的数据源类型"):
        DataSourceEngineFactory().build_config(ds)


@patch("app.services.datasource_engine_factory.create_engine")
@patch("app.services.datasource_engine_factory.decrypt_password", return_value="secret")
def test_create_engine_uses_pool_defaults(mock_decrypt, mock_create_engine, ds):
    factory = DataSourceEngineFactory()
    factory.create_engine(ds)

    _, kwargs = mock_create_engine.call_args
    assert mock_create_engine.call_args[0][0] == "mysql+pymysql://user:secret@db-host:3306/reporting"
    assert kwargs["poolclass"] is QueuePool
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == 3600
    assert kwargs["connect_args"] == {}
