// frontend/src/api/scheduledReports.js
import request from "@/utils/request"

export function listReports(params) {
  return request.get('/scheduled-reports/', { params })
}

export function getReport(id) {
  return request.get(`/scheduled-reports/${id}`)
}

export function createReport(data) {
  return request.post('/scheduled-reports/', data)
}

export function updateReport(id, data) {
  return request.put(`/scheduled-reports/${id}`, data)
}

export function deleteReport(id) {
  return request.delete(`/scheduled-reports/${id}`)
}

export function toggleReport(id, enabled) {
  return request.post(`/scheduled-reports/${id}/toggle`, { enabled })
}

export function runNow(id) {
  return request.post(`/scheduled-reports/${id}/run-now`)
}

export function getDeliveries(id, params) {
  return request.get(`/scheduled-reports/${id}/deliveries`, { params })
}

export function getNextRunTime(cron) {
  return request.get(`/scheduled-reports/cron/next/${encodeURIComponent(cron)}`)
}
