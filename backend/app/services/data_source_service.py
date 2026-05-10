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
        
        # 处理更新数据：使用 exclude_unset=True 但后端需要更新布尔字段
        update_data = ds_data.model_dump(exclude_unset=True)
        
        # 手动添加前端传来的布尔字段（即使值为 False）
        if hasattr(ds_data, 'use_proxy'):
            update_data['use_proxy'] = ds_data.use_proxy
        if hasattr(ds_data, 'proxy_server_id') and ds_data.proxy_server_id is not None:
            update_data['proxy_server_id'] = ds_data.proxy_server_id
        
        # 检查密码是否需要更新
        password_value = update_data.get('password')
        if password_value:  # 有新密码
            from app.core.security import encrypt_password
            update_data['password_encrypted'] = encrypt_password(password_value)
            del update_data['password']
        
        updated_ds = self.ds_repo.update(db_ds, update_data)
        return DataSourceResponse.model_validate(updated_ds)

    def delete_data_source(self, ds_id: int) -> bool:
        """删除数据源"""
        db_ds = self.ds_repo.get_by_id(ds_id)
        if not db_ds:
            return False
        return self.ds_repo.delete(db_ds)

    def test_connection(self, request: DataSourceTestRequest) -> DataSourceTestResponse:
        """测试数据源连接（支持 HTTP 代理）"""
        try:
            ds_type = request.type.upper() if request.type else ""
            
            # 获取代理配置
            proxy_info = None
            if request.use_proxy and request.proxy_server_id:
                from app.repositories.proxy_server_repository import ProxyServerRepository
                proxy_repo = ProxyServerRepository(self.ds_repo.db)
                proxy = proxy_repo.get_by_id(request.proxy_server_id)
                if proxy and proxy.is_active:
                    proxy_info = {
                        "host": proxy.host,
                        "port": proxy.port,
                        "type": proxy.proxy_type
                    }
            
# 测试 MySQL/Doris 连接
            if ds_type in ("MYSQL", "DORIS"):
                import pymysql
                import subprocess
                import socket
                import socks
                
                # 如果有代理，测试代理是否可达
                if proxy_info:
                    if proxy_info["type"] == "http":
                        proxy_url = f"http://{proxy_info['host']}:{proxy_info['port']}"
                        test_cmd = f"curl --noproxy '*' -x {proxy_url} --connect-timeout 10 -s -o /dev/null -w '%{{http_code}}' http://{request.host}:{request.port}/"
                        try:
                            result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=15)
                            if result.returncode != 0 or result.stdout.strip() == "000":
                                return DataSourceTestResponse(success=False, message=f"通过代理无法连接到目标服务器 {request.host}:{request.port}")
                        except Exception:
                            pass
                    elif proxy_info["type"] == "socks5":
                        # SOCKS5 代理：测试公网连通性
                        test_cmd = f"curl --noproxy '*' --socks5 {proxy_info['host']}:{proxy_info['port']} --connect-timeout 10 -s -o /dev/null -w '%{{http_code}}' https://www.baidu.com"
                        try:
                            result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=15)
                            if result.returncode != 0 or result.stdout.strip() != "200":
                                return DataSourceTestResponse(success=False, message=f"SOCKS5代理不可达")
                        except Exception as e:
                            return DataSourceTestResponse(success=False, message=f"SOCKS5代理测试失败: {str(e)}")
                
                # 使用代理连接
                try:
                    if proxy_info and proxy_info["type"] == "socks5":
                        # 全局替换 socket 为 SOCKS5 代理 socket
                        import socks
                        original_socket = socket.socket
                        socks.set_default_proxy(socks.SOCKS5, proxy_info["host"], proxy_info["port"])
                        socket.socket = socks.socksocket
                        try:
                            conn = pymysql.connect(
                                host=request.host,
                                port=request.port,
                                user=request.username,
                                password=request.password,
                                database=request.database,
                                connect_timeout=20
                            )
                            conn.close()
                            return DataSourceTestResponse(success=True, message="连接成功（通过SOCKS5代理）")
                        finally:
                            # 恢复原始 socket
                            socket.socket = original_socket
                            socks.set_default_proxy()  # 清除默认代理
                    else:
                        # 直接连接
                        conn = pymysql.connect(
                            host=request.host,
                            port=request.port,
                            user=request.username,
                            password=request.password,
                            database=request.database,
                            connect_timeout=15
                        )
                        conn.close()
                        msg = "连接成功" + ("（通过代理）" if proxy_info else "")
                        return DataSourceTestResponse(success=True, message=msg)
                except Exception as e:
                    err_msg = str(e)
                    if "timed out" in err_msg.lower():
                        if proxy_info:
                            return DataSourceTestResponse(success=False, message=f"连接超时。代理已配置但目标仍不可达，可能是目标服务器不可访问")
                        return DataSourceTestResponse(success=False, message=f"连接超时: {request.host}:{request.port} 无法访问")
                    return DataSourceTestResponse(success=False, message=f"连接失败: {err_msg}")
            
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
                    msg = "连接成功" + ("（通过代理）" if proxy_info else "")
                    return DataSourceTestResponse(success=True, message=msg)
                except Exception as e:
                    return DataSourceTestResponse(success=False, message=f"连接失败: {str(e)}")
            else:
                return DataSourceTestResponse(success=False, message=f"不支持的数据源类型: {request.type}")
        except Exception as e:
            return DataSourceTestResponse(success=False, message=f"连接失败: {str(e)}")