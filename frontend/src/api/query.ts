import request from "@/utils/request"
import type { PaginatedResponse } from "@/types/api"

export interface SQLQueryRequest {
  sql: string
  data_source_id: number
  params?: Record<string, unknown>
  page?: number
  page_size?: number
  timeout?: number
}

export interface QueryResult {
  columns: string[]
  rows: unknown[][]
  total: number
  execution_time_ms: number
  page?: number
  page_size?: number
  total_pages?: number
  has_more?: boolean
  cursor?: string
}

export interface QueryHistoryItem {
  id: number
  sql: string
  data_source_id: number
  data_source_name?: string
  execution_time_ms: number
  row_count: number
  created_at: string
  status: string
}

export function executeSQL(data: SQLQueryRequest): Promise<QueryResult> {
  return request({
    url: "/query/sql",
    method: "post",
    data
  }) as Promise<QueryResult>
}

/** Alias for executeSQL */
export const executeQuery = executeSQL

export function getQueryHistory(params?: {
  page?: number
  page_size?: number
  data_source_id?: number
}): Promise<PaginatedResponse<QueryHistoryItem>> {
  return request({
    url: "/query/history",
    method: "get",
    params
  }) as Promise<PaginatedResponse<QueryHistoryItem>>
}
