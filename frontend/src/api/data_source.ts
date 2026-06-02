import request from "@/utils/request"

export interface DataSource {
  id: number
  name: string
  type: string
  host: string
  port: number
  database: string
  username: string
  is_active: boolean
  use_proxy?: boolean
  proxy_server_id?: number
  load_group?: boolean
  created_by: number
  created_at: string
  updated_at: string
}

export interface DataSourceCreate {
  name: string
  type: string
  host: string
  port: number
  database: string
  username: string
  password?: string
  is_active?: boolean
  use_proxy?: boolean
  proxy_server_id?: number
  load_group?: boolean
}

export interface DataSourceUpdate {
  name?: string
  type?: string
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  is_active?: boolean
  use_proxy?: boolean
  proxy_server_id?: number | null
  load_group?: boolean
}

export interface DataSourceTestRequest {
  type: string
  host: string
  port: number
  database: string
  username: string
  password?: string
  use_proxy?: boolean
  proxy_server_id?: number
}

export interface DataSourceTestResponse {
  success: boolean
  message: string
}

export function getDataSourceList(params?: {
  page?: number
  page_size?: number
}): Promise<DataSource[]> {
  return request({
    url: "/datasources",
    method: "get",
    params
  }) as Promise<DataSource[]>
}

export function getDataSource(id: number): Promise<DataSource> {
  return request({
    url: `/datasources/${id}`,
    method: "get"
  }) as Promise<DataSource>
}

export function createDataSource(data: DataSourceCreate): Promise<DataSource> {
  return request({
    url: "/datasources",
    method: "post",
    data
  }) as Promise<DataSource>
}

export function updateDataSource(id: number, data: DataSourceUpdate): Promise<DataSource> {
  return request({
    url: `/datasources/${id}`,
    method: "put",
    data
  }) as Promise<DataSource>
}

export function deleteDataSource(id: number): Promise<void> {
  return request({
    url: `/datasources/${id}`,
    method: "delete"
  }) as Promise<void>
}

export function testDataSourceConnection(data: DataSourceTestRequest): Promise<DataSourceTestResponse> {
  return request({
    url: "/datasources/test",
    method: "post",
    data
  }) as Promise<DataSourceTestResponse>
}
