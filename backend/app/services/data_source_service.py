from sqlalchemy.orm import Session
from typing import List, Optional
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate, DataSourceResponse, DataSourceTestRequest, DataSourceTestResponse


class DataSourceService:
    def __init__(self, db: Session):
        self.ds_repo = DataSourceRepository(db)

    def create_data_source(self, ds_data: DataSourceCreate, user_id: int) -> DataSourceResponse:
        """创建数据源"""
        test_result = self.test_connection(DataSourceTestRequest(
            type=ds_data.type,
            host=ds_data.host,
            port=ds_data.port,
            database=ds_data.database,
            username=ds_data.username,
            password=ds_data.password
        ))
        if not test_result.success:
            raise ValueError(f"连接测试失败: {test_result.message}")

        db_ds = self.ds_repo.create(ds_data.model_dump(), user_id)
        return DataSourceResponse.model_validate(db_ds)

    def get_data_source(self, ds_id: int) -> Optional[DataSourceResponse]:
        """获取数据源"""
        db_ds = self.ds_repo.get_by_id(ds_id)
        if not db_ds:
            return None
        return DataSourceResponse.model_validate(db_ds)

    def list_data_sources(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[DataSourceResponse]:
        """列出数据源"""
        if user_id:
            db_dss = self.ds_repo.get_by_user(user_id, skip, limit)
        else:
            db_dss = self.ds_repo.get_all(skip, limit)

        return [DataSourceResponse.model_validate(ds) for ds in db_dss]

    def update_data_source(self, ds_id: int, ds_data: DataSourceUpdate) -> Optional[DataSourceResponse]:
        """更新数据源"""
        db_ds = self.ds_repo.get_by_id(ds_id)
        if not db_ds:
            return None

        updated_ds = self.ds_repo.update(db_ds, ds_data.model_dump(exclude_unset=True))
        return DataSourceResponse.model_validate(updated_ds)

    def delete_data_source(self, ds_id: int) -> bool:
        """删除数据源"""
        db_ds = self.ds_repo.get_by_id(ds_id)
        if not db_ds:
            return False
        return self.ds_repo.delete(db_ds)

    def test_connection(self, request: DataSourceTestRequest) -> DataSourceTestResponse:
        """测试数据源连接"""
        try:
            if request.type == "MYSQL":
                import pymysql
                conn = pymysql.connect(
                    host=request.host,
                    port=request.port,
                    user=request.username,
                    password=request.password,
                    database=request.database,
                    connect_timeout=5
                )
                conn.close()
                return DataSourceTestResponse(success=True, message="连接成功")
            elif request.type == "POSTGRESQL":
                import psycopg2
                conn = psycopg2.connect(
                    host=request.host,
                    port=request.port,
                    user=request.username,
                    password=request.password,
                    database=request.database,
                    connect_timeout=5
                )
                conn.close()
                return DataSourceTestResponse(success=True, message="连接成功")
            elif request.type.upper() == "POSTGRESQL":
                import psycopg2
                conn = psycopg2.connect(
                    host=request.host,
                    port=request.port,
                    user=request.username,
                    password=request.password,
                    database=request.database,
                    connect_timeout=5
                )
                conn.close()
                return DataSourceTestResponse(success=True, message="连接成功")
            elif request.type == "DORIS":
                import pymysql
                conn = pymysql.connect(
                    host=request.host,
                    port=request.port,
                    user=request.username,
                    password=request.password,
                    database=request.database,
                    connect_timeout=5
                )
                conn.close()
                return DataSourceTestResponse(success=True, message="连接成功")
            else:
                return DataSourceTestResponse(success=False, message=f"不支持的数据源类型: {request.type}")
        except Exception as e:
            return DataSourceTestResponse(success=False, message=f"连接失败: {str(e)}")
