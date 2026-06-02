import request from "@/utils/request"
import type { DataWrapper, PaginatedResponse } from "@/types/api"

export interface FrontendConfig {
  nl2sql_timeout: number
  nl2sql_timeout_ms: number
  llm_adapter: string
  llm_provider: string
  llm_model: string
  llm_api_mode: string
  nl2sql_structured_output_enabled: boolean
  nl2sql_schema_retrieval_enabled: boolean
  nl2sql_schema_retrieval_min_chars: number
  nl2sql_schema_retrieval_max_sections: number
}

export interface NL2SQLRequest {
  question: string
  data_source_id: number
  group_id?: number
  context?: string
}

export interface SQLSuggestion {
  sql: string
  confidence: number
  explanation: string
  chart_config?: {
    chart_type: string
    x_axis: string
    y_axis: string
    reason: string
  }
}

export interface NL2SQLResponse {
  suggestions: SQLSuggestion[]
  selected_sql: string
  query_result?: {
    columns: string[]
    rows: unknown[][]
    total: number
    execution_time_ms: number
  }
  llm_used: boolean
  execution_time_ms: number
}

export interface GroupInfo {
  group_id: number
  group_name: string
}

// ── Cached frontend config ────────────────────────────────

let frontendConfigCache: FrontendConfig | null = null
let configLoaded = false

/**
 * Fetch frontend configuration (NL2SQL timeout, etc.)
 * Cached after first load.
 */
export async function getFrontendConfig(): Promise<FrontendConfig> {
  if (configLoaded && frontendConfigCache) {
    return frontendConfigCache
  }

  try {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch('/api/config', { method: 'GET', headers })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const data: FrontendConfig = await response.json()
    frontendConfigCache = data
    configLoaded = true
    return data
  } catch (error) {
    console.warn('[NL2SQL] Failed to load frontend config, using defaults:', error)
    const defaults: FrontendConfig = {
      nl2sql_timeout: 300,
      nl2sql_timeout_ms: 360000,
      llm_adapter: 'raw',
      llm_provider: 'openai',
      llm_model: 'gpt-3.5-turbo',
      llm_api_mode: 'chat',
      nl2sql_structured_output_enabled: false,
      nl2sql_schema_retrieval_enabled: true,
      nl2sql_schema_retrieval_min_chars: 12000,
      nl2sql_schema_retrieval_max_sections: 8,
    }
    return defaults
  }
}

/**
 * Get NL2SQL request timeout in milliseconds.
 */
export async function getNL2SQLTimeout(): Promise<number> {
  const config = await getFrontendConfig()
  return config.nl2sql_timeout_ms
}

export function parseQuestion(data: NL2SQLRequest): Promise<NL2SQLResponse> {
  const requestId = `nl2sql_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  const startTime = performance.now()

  console.group(`[NL2SQL] 📤 Request | ${requestId}`)
  console.log('├─ data_source_id:', data.data_source_id)
  console.log('├─ question:', data.question)
  console.groupEnd()

  return getNL2SQLTimeout().then((timeout) => {
    return request({
      url: "/nl2sql/parse",
      method: "post",
      data,
      timeout,
    }) as Promise<NL2SQLResponse>
  }).then((response) => {
    const endTime = performance.now()
    console.group(`[NL2SQL] ✅ Success | ${requestId}`)
    console.log('├─ duration:', `${(endTime - startTime).toFixed(2)}ms`)
    console.log('├─ SQL suggestions:', response.suggestions?.length ?? 0)
    console.log('├─ selected SQL:', response.selected_sql)
    console.groupEnd()
    return response
  }).catch((error) => {
    const endTime = performance.now()
    console.group(`[NL2SQL] ❌ Failed | ${requestId}`)
    console.log('├─ duration:', `${(endTime - startTime).toFixed(2)}ms`)
    console.log('├─ error:', error.message || error)
    console.groupEnd()
    throw error
  })
}

/**
 * Get group list for a data source.
 */
export function getGroups(dataSourceId: number): Promise<GroupInfo[]> {
  return request({
    url: "/nl2sql/groups",
    method: "get",
    params: { data_source_id: dataSourceId }
  }).then((response: unknown) => {
    const res = response as DataWrapper<GroupInfo[]>
    return res.data || []
  })
}
