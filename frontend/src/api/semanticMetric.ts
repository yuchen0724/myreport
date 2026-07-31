import request from "@/utils/request"

export interface SemanticMetric {
  id: number
  metric_key: string
  name: string
  description?: string
  data_source_id: number
  base_sql: string
  metric_expression: string
  dimensions: string[]
  time_column?: string
  is_active: boolean
  created_by: number
  created_at: string
}

export function getMetricList(params?: Record<string, unknown>): Promise<SemanticMetric[]> {
  return request({ url: "/semantic-metrics", method: "get", params }) as Promise<SemanticMetric[]>
}

export function getMetric(id: number): Promise<SemanticMetric> {
  return request({ url: `/semantic-metrics/${id}`, method: "get" }) as Promise<SemanticMetric>
}

export function createMetric(data: Partial<SemanticMetric>): Promise<SemanticMetric> {
  return request({ url: "/semantic-metrics", method: "post", data }) as Promise<SemanticMetric>
}

export function updateMetric(id: number, data: Partial<SemanticMetric>): Promise<SemanticMetric> {
  return request({ url: `/semantic-metrics/${id}`, method: "put", data }) as Promise<SemanticMetric>
}

export function deleteMetric(id: number): Promise<void> {
  return request({ url: `/semantic-metrics/${id}`, method: "delete" }) as Promise<void>
}

// ── Legacy name aliases (used by .vue imports) ────────────
export const getSemanticMetrics = getMetricList
export const updateSemanticMetric = updateMetric
export function executeSemanticMetricQuery(data: { metric_key: string; filters?: Record<string, unknown> }): Promise<{ metric: SemanticMetric; query: Record<string, any> }> {
  return request({ url: "/semantic-metrics/query/execute", method: "post", data }) as Promise<{ metric: SemanticMetric; query: Record<string, any> }>
}
export const createSemanticMetric = createMetric
export const deleteSemanticMetric = deleteMetric
export function previewSemanticMetricQuery(data: { metric_key: string; sql?: string }): Promise<{ data_source_id: number; sql: string; params: Record<string, unknown> }> {
  return request({ url: "/semantic-metrics/query/preview", method: "post", data }) as Promise<{ data_source_id: number; sql: string; params: Record<string, unknown> }>
}
