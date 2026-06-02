import request from "@/utils/request"

export interface RcaConfig {
  id: number
  metric_key: string
  name: string
  data_source_id: number
  anomaly_threshold: number
  drill_levels: number
  is_active: boolean
}

export interface RcaAnomaly {
  id: number
  metric_key: string
  anomaly_value: number
  expected_value: number
  deviation_pct: number
  dimension: string
  dimension_value: string
  detected_at: string
}

export function getRcaConfigs(): Promise<RcaConfig[]> {
  return request({ url: "/rca/configs", method: "get" }) as Promise<RcaConfig[]>
}

export function createRcaConfig(data: Partial<RcaConfig>): Promise<RcaConfig> {
  return request({ url: "/rca/configs", method: "post", data }) as Promise<RcaConfig>
}

export function triggerRca(data: { config_id: number; date_from: string; date_to: string }): Promise<{ task_id: string }> {
  return request({ url: "/rca/analyze", method: "post", data }) as Promise<{ task_id: string }>
}

export function getRcaResult(taskId: string): Promise<RcaAnomaly[]> {
  return request({ url: `/rca/result/${taskId}`, method: "get" }) as Promise<RcaAnomaly[]>
}

export function updateRcaConfig(configId: number, data: Partial<RcaConfig>): Promise<RcaConfig> {
  return request({ url: `/rca/configs/${configId}`, method: "put", data }) as Promise<RcaConfig>
}
export function deleteRcaConfig(configId: number): Promise<void> {
  return request({ url: `/rca/configs/${configId}`, method: "delete" }) as Promise<void>
}
export function getRcaTasks(params?: Record<string, unknown>): Promise<{ id: number; task_id: string; status: string; created_at: string }[]> {
  return request({ url: "/rca/tasks", method: "get", params }) as Promise<{ id: number; task_id: string; status: string; created_at: string }[]>
}
export function deleteRcaTask(taskId: string): Promise<void> {
  return request({ url: `/rca/tasks/${taskId}`, method: "delete" }) as Promise<void>
}
export function triggerRcaAnalyze(data: { metric_config_id: number; analysis_date: string; period_days?: number }): Promise<{ task_id: string }> {
  return triggerRca({ config_id: data.metric_config_id, date_from: data.analysis_date, date_to: data.analysis_date })
}

// ── Legacy name aliases ───────────────────────────────────
export const getRcaTask = getRcaResult
export const getRcaAnomalies = getRcaResult
export function rcaDrillDown(data: { task_id: string; dimension: string; dimension_value: string }): Promise<RcaAnomaly[]> {
  return request({ url: "/rca/drilldown", method: "post", data }) as Promise<RcaAnomaly[]>
}
export function rcaAiAnalysis(data: { task_id: string }): Promise<{ analysis: string }> {
  return request({ url: "/rca/analyze-ai", method: "post", data }) as Promise<{ analysis: string }>
}
