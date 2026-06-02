from sqlalchemy.orm import Session
from typing import List, Optional
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate, DataSourceResponse, DataSourceTestRequest, DataSourceTestResponse
from app.exceptions import NotFoundError, AuthorizationError


class DataSourceService:
    def __init__(self, db: Session):
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

    def update_data_source(self, ds_id: int, ds_data: DataSourceUpdate, user_id: int) -> Optional[DataSourceResponse]:
        """更新数据源"""
        db_ds = self._require_data_source(ds_id)
        self._check_owner(db_ds, user_id)
        
        # 处理更新数据：使用 exclude_unset=True 但后端需要更新布尔字段
        update_data = ds_data.model_dump(exclude_unset=True)
        
        # 手动添加前端传来的布尔字段（即使值为 False）
        if hasattr(ds_data, 'use_proxy'):
            update_data['use_proxy'] = ds_data.use_proxy
        if hasattr(ds_data, 'proxy_server_id') and ds_data.proxy_server_id is not None:
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
            # 代理设置统一由 socks_proxy_context 处理
            
            # 测试 MySQL/Doris 连接
            if ds_type in ("MYSQL", "DORIS"):
                import pymysql
                import subprocess
                
                # 获取代理配置用于前置检查
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
                
                # HTTP 代理前置检查 curl 测试
                if proxy_type == "http":
                    proxy_url = f"http://{proxy_host}:{proxy_port}"
                    test_cmd = f"curl --noproxy '*' -x {proxy_url} --connect-timeout 10 -s -o /dev/null -w '%{{http_code}}' http://{request.host}:{request.port}/"
                    try:
                        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=15)
                        if result.returncode != 0 or result.stdout.strip() == "000":
                            return DataSourceTestResponse(success=False, message=f"通过代理无法连接到目标服务器 {request.host}:{request.port}")
                    except Exception:
                        pass
                elif proxy_type == "socks5":
                    # SOCKS5 前置检查：测试代理是否可达
                    test_cmd = f"curl --noproxy '*' --socks5 {proxy_host}:{proxy_port} --connect-timeout 10 -s -o /dev/null -w '%{{http_code}}' https://www.baidu.com"
                    try:
                        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=15)
                        if result.returncode != 0 or result.stdout.strip() != "200":
                            return DataSourceTestResponse(success=False, message=f"SOCKS5代理不可达")
                    except Exception as e:
                        return DataSourceTestResponse(success=False, message=f"SOCKS5代理测试失败: {str(e)}")
                
                # 实际连接测试（engine 级别代理，无全局 socket 污染）
                from urllib.parse import quote_plus
                encoded_password = quote_plus(request.password)

                if proxy_type == "socks5":
                    from app.utils.db_executor import create_socks_engine
                    from sqlalchemy import text
                    conn_url = f"mysql+pymysql://{request.username}:{encoded_password}@{request.host}:{request.port}/{request.database}"
                    engine, _ = create_socks_engine(
                        conn_url, proxy_host, proxy_port,
                        pool_size=1, max_overflow=0,
                    )
                    try:
                        with engine.connect() as conn:
                            conn.execute(text("SELECT 1"))
                        return DataSourceTestResponse(
                            success=True,
                            message="连接成功（通过SOCKS5代理）"
                        )
                    finally:
                        engine.dispose()
                else:
                    conn = pymysql.connect(
                        host=request.host,
                        port=request.port,
                        user=request.username,
                        password=request.password,
                        database=request.database,
                        connect_timeout=20
                    )
                    conn.close()
                    msg = "连接成功"
                    if proxy_type == "http":
                        msg += "（通过HTTP代理）"
                    elif use_proxy:
                        msg += f"（通过代理）"
                    return DataSourceTestResponse(success=True, message=msg)
            
            # PostgreSQL 连接
            elif ds_type == "POSTGRESQL":
                import psycopg2
                try:
                    conn = psycopg2.connect(
                        host=request.host,
                        port=request.port,
                        user=request.username,
                        password=request.password,
                        database=request.database,
                        connect_timeout=15
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