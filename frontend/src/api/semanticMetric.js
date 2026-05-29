import request from "@/utils/request"

export function getSemanticMetrics(params) {
  return request({
    url: "/semantic-metrics",
    method: "get",
    params
  })
}

export function createSemanticMetric(data) {
  return request({
    url: "/semantic-metrics",
    method: "post",
    data
  })
}

export function updateSemanticMetric(id, data) {
  return request({
    url: `/semantic-metrics/${id}`,
    method: "put",
    data
  })
}

export function deleteSemanticMetric(id) {
  return request({
    url: `/semantic-metrics/${id}`,
    method: "delete"
  })
}

export function previewSemanticMetricQuery(data) {
  return request({
    url: "/semantic-metrics/query/preview",
    method: "post",
    data
  })
}

export function executeSemanticMetricQuery(data) {
  return request({
    url: "/semantic-metrics/query/execute",
    method: "post",
    data
  })
}
