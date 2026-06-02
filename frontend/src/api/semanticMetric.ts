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
  return request({ url: "/metrics", method: "get", params }) as Promise<SemanticMetric[]>
}

export function getMetric(id: number): Promise<SemanticMetric> {
  return request({ url: `/metrics/${id}`, method: "get" }) as Promise<SemanticMetric>
}

export function createMetric(data: Partial<SemanticMetric>): Promise<SemanticMetric> {
  return request({ url: "/metrics", method: "post", data }) as Promise<SemanticMetric>
}

export function updateMetric(id: number, data: Partial<SemanticMetric>): Promise<SemanticMetric> {
  return request({ url: `/metrics/${id}`, method: "put", data }) as Promise<SemanticMetric>
}

export function deleteMetric(id: number): Promise<void> {
  return request({ url: `/metrics/${id}`, method: "delete" }) as Promise<void>
}

// ── Legacy name aliases (used by .vue imports) ────────────
export const getSemanticMetrics = getMetricList
export const updateSemanticMetric = updateMetric
export function executeSemanticMetricQuery(data: { metric_key: string; filters?: Record<string, unknown> }): Promise<Record<string, unknown>> {
  return request({ url: "/metrics/query", method: "post", data }) as Promise<Record<string, unknown>>
}
export const createSemanticMetric = createMetric
export const deleteSemanticMetric = deleteMetric
export function previewSemanticMetricQuery(data: { metric_key: string; sql?: string }): Promise<{ columns: string[]; rows: unknown[][] }> {
  return request({ url: "/metrics/preview", method: "post", data }) as Promise<{ columns: string[]; rows: unknown[][] }>
}
