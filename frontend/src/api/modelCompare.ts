import request from "@/utils/request"

export interface ModelInfo {
  id: number
  name: string
  type: string
  status: string
  metrics?: Record<string, number>
  created_at: string
}

export function compareModels(data: { model_ids: number[] }): Promise<Record<string, unknown>> {
  return request({ url: "/model-compare", method: "post", data }) as Promise<Record<string, unknown>>
}

export function getModelList(params?: Record<string, unknown>): Promise<ModelInfo[]> {
  return request({ url: "/model-compare/models", method: "get", params }) as Promise<ModelInfo[]>
}

// ── Legacy name aliases ───────────────────────────────────
export const startCompare = compareModels
export function getCompareStatus(taskId: string): Promise<Record<string, unknown>> {
  return request({ url: `/model-compare/status/${taskId}`, method: "get" }) as Promise<Record<string, unknown>>
}
