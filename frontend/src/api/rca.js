import request from "@/utils/request"

export function getRcaConfigs() {
  return request({ url: "/rca/configs", method: "get" })
}

export function createRcaConfig(data) {
  return request({ url: "/rca/configs", method: "post", data })
}

export function updateRcaConfig(id, data) {
  return request({ url: `/rca/configs/${id}`, method: "put", data })
}

export function deleteRcaConfig(id) {
  return request({ url: `/rca/configs/${id}`, method: "delete" })
}

export function triggerRcaAnalyze(data) {
  return request({ url: "/rca/analyze", method: "post", data })
}

export function getRcaTasks(params) {
  return request({ url: "/rca/tasks", method: "get", params })
}

export function deleteRcaTask(taskId) {
  return request({ url: `/rca/tasks/${taskId}`, method: "delete" })
}

export function getRcaTask(taskId) {
  return request({ url: `/rca/tasks/${taskId}`, method: "get" })
}

export function getRcaAnomalies(taskId) {
  return request({ url: `/rca/tasks/${taskId}/anomalies`, method: "get" })
}

export function rcaDrillDown(data) {
  return request({ url: "/rca/drill-down", method: "post", data })
}

export function rcaAiAnalysis(taskId) {
  return fetch(`/api/rca/tasks/${taskId}/ai-analysis`)
}
