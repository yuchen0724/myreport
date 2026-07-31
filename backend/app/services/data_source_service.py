from sqlalchemy.orm import Session
from typing import List, Optional
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate, DataSourceResponse, DataSourceTestRequest, DataSourceTestResponse
from app.exceptions import NotFoundError, AuthorizationError


class DataSourceService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)

    def _require_data_source(self, ds_id: int) -> DataSourceResponse:
        """获取数据源，不存在则抛出 NotFoundError"""
        db_ds = self.ds_repo.get_by_id(ds_id)
        if not db_ds:
            raise NotFoundError(f"数据源不存在 (id={ds_id})")
        return db_ds

    def _check_owner(self, ds, user_id: int) -> None:
        """校验当前用户是否为数据源所有者

        created_by 为 NULL 时也拒绝，防止未标记所有者的数据源被任何人访问。
        """
        if not ds.created_by or ds.created_by != user_id:
            raise AuthorizationError("您没有权限操作此数据源")

    def require_access(self, ds_id: int, user_id: int):
        """Return a data source only when the user owns it or is an administrator."""
        db_ds = self._require_data_source(ds_id)
        if db_ds.created_by == user_id:
            return db_ds

        from app.models.user import User

        user = self.db.query(User).filter(User.id == user_id).first()
        is_admin = bool(user and user.role and user.role.name == "admin")
        if not is_admin:
            raise AuthorizationError("您没有权限访问此数据源")
        return db_ds

    def create_data_source(self, ds_data: DataSourceCreate, user_id: int) -> DataSourceResponse:
        """创建数据源"""
        test_result = self.test_connection(DataSourceTestRequest(
            type=ds_data.type,
            host=ds_data.host,
            port=ds_data.port,
            database=ds_data.database,
            username=ds_data.username,
            password=ds_data.password,
            use_proxy=ds_data.use_proxy,
            proxy_server_id=ds_data.proxy_server_id,
        ))
        if not test_result.success:
            raise ValueError(f"连接测试失败: {test_result.message}")

        db_ds = self.ds_repo.create(ds_data.model_dump(), user_id)
        return DataSourceResponse.model_validate(db_ds)

    def get_data_source(self, ds_id: int, user_id: int) -> Optional[DataSourceResponse]:
        """获取数据源"""
        db_ds = self.require_access(ds_id, user_id)
        return DataSourceResponse.model_validate(db_ds)

    def list_data_sources(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[DataSourceResponse]:
        """列出数据源"""
        if user_id:
            db_dss = self.ds_repo.get_by_user(user_id, skip, limit)
        else:
            db_dss = self.ds_repo.get_all(skip, limit)

        return [DataSourceResponse.model_validate(ds) for ds in db_dss]

    def update_data_source(self, ds_id: int, ds_data: DataSourceUpdate, user_id: int) -> Optional[DataSourceResponse]:
        """更新数据源"""
        db_ds = self._require_data_source(ds_id)
        self._check_owner(db_ds, user_id)
        
        # 处理更新数据：使用 exclude_unset=True 但后端需要更新布尔字段
        update_data = ds_data.model_dump(exclude_unset=True)
        
        # 手动添加前端传来的布尔/空值字段（即使值为 False/None）
        if hasattr(ds_data, 'use_proxy'):
            update_data['use_proxy'] = ds_data.use_proxy
        if hasattr(ds_data, 'proxy_server_id'):
            update_data['proxy_server_id'] = ds_data.proxy_server_id
        if hasattr(ds_data, 'load_group') and ds_data.load_group is not None:
            update_data['load_group'] = ds_data.load_group
        
        # 检查密码是否需要更新
        password_value = update_data.get('password')
        if password_value:  # 有新密码
            from app.core.security import encrypt_password
            update_data['password_encrypted'] = encrypt_password(password_value)
            del update_data['password']
        
        updated_ds = self.ds_repo.update(db_ds, update_data)
        return DataSourceResponse.model_validate(updated_ds)

    def delete_data_source(self, ds_id: int, user_id: int) -> bool:
        """删除数据源"""
        db_ds = self._require_data_source(ds_id)
        self._check_owner(db_ds, user_id)
        return self.ds_repo.delete(db_ds)

    def test_connection(self, request: DataSourceTestRequest) -> DataSourceTestResponse:
        """测试数据源连接（支持 HTTP/SOCKS5 代理）"""
        try:
            ds_type = request.type.upper() if request.type else ""
            
            # 测试 MySQL/Doris 连接
            if ds_type in ("MYSQL", "DORIS"):
                import pymysql
                from urllib.parse import quote_plus
                
                # 获取代理配置
                proxy_host = None
                proxy_port = None
                proxy_type = None
                use_proxy = request.use_proxy and request.proxy_server_id
                if use_proxy:
                    from app.repositories.proxy_server_repository import ProxyServerRepository
                    proxy_repo = ProxyServerRepository(self.ds_repo.db)
                    p = proxy_repo.get_by_id(request.proxy_server_id)
                    if p and p.is_active:
                        proxy_host = p.host
                        proxy_port = p.port
                        proxy_type = p.proxy_type
                
                encoded_password = quote_plus(request.password)
                test_start = __import__("time").time()
                
                if proxy_type == "socks5":
                    from app.utils.db_executor import build_pymysql_socks_creator
                    from sqlalchemy import create_engine, text
                    from sqlalchemy.pool import QueuePool
                    conn_url = f"mysql+pymysql://{request.username}:{encoded_password}@{request.host}:{request.port}/{request.database}"
                    creator = build_pymysql_socks_creator(
                        proxy_host=proxy_host, proxy_port=proxy_port,
                        host=request.host, port=request.port,
                        username=request.username, password=request.password,
                        database=request.database, connect_timeout=10,
                    )
                    engine = create_engine(
                        conn_url, poolclass=QueuePool, pool_size=1, max_overflow=0,
                        creator=creator,
                    )
                    try:
                        with engine.connect() as conn:
                            conn.execute(text("SELECT 1"))
                        elapsed = (__import__("time").time() - test_start) * 1000
                        return DataSourceTestResponse(
                            success=True,
                            message=f"连接成功（通过SOCKS5代理，{elapsed:.0f}ms）"
                        )
                    except Exception as e:
                        err_msg = self._format_conn_error(e, request.host, request.port)
                        return DataSourceTestResponse(success=False, message=err_msg)
                    finally:
                        engine.dispose()
                elif proxy_type == "http":
                    return DataSourceTestResponse(
                        success=False,
                        message="数据库连接不支持 HTTP 代理，请改用 SOCKS5 代理",
                    )
                else:
                    # 无代理直连
                    conn = pymysql.connect(
                        host=request.host, port=request.port,
                        user=request.username, password=request.password,
                        database=request.database, connect_timeout=10,
                    )
                    conn.close()
                    return DataSourceTestResponse(success=True, message="连接成功")
            
            # PostgreSQL 连接
            elif ds_type == "POSTGRESQL":
                import psycopg2
                try:
                    conn = psycopg2.connect(
                        host=request.host, port=request.port,
                        user=request.username, password=request.password,
                        database=request.database, connect_timeout=10,
                    )
                    conn.close()
                    return DataSourceTestResponse(success=True, message="连接成功")
                except Exception as e:
                    return DataSourceTestResponse(success=False, message=f"连接失败: {str(e)}")
            else:
                return DataSourceTestResponse(success=False, message=f"不支持的数据源类型: {request.type}")
        except Exception as e:
            err_msg = str(e)
            if "timed out" in err_msg.lower():
                return DataSourceTestResponse(success=False, message=f"连接超时: {request.host}:{request.port} 无法访问")
            return DataSourceTestResponse(success=False, message=f"连接失败: {err_msg}")

    @staticmethod
    def _format_conn_error(e: Exception, host: str, port: int) -> str:
        """格式化连接错误信息"""
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            return f"连接超时: {host}:{port} 无法访问"
        if "Connection refused" in err_msg:
            return f"连接被拒绝: {host}:{port} 端口未开放"
        if "Unknown host" in err_msg or "Name or service not known" in err_msg:
            return f"无法解析主机: {host}"
        if "Access denied" in err_msg:
            return "用户名或密码错误"
        if "Unknown database" in err_msg:
            return "数据库不存在"
        return f"连接失败: {err_msg}"
