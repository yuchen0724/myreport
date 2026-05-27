// frontend/src/api/subscriptions.js
import request from "@/utils/request"

export function listSubscriptions(params) {
  return request.get('/subscriptions', { params })
}

export function getSubscription(id) {
  return request.get(`/subscriptions/${id}`)
}

export function createSubscription(data) {
  return request.post('/subscriptions', data)
}

export function updateSubscription(id, data) {
  return request.put(`/subscriptions/${id}`, data)
}

export function deleteSubscription(id) {
  return request.delete(`/subscriptions/${id}`)
}

export function toggleSubscription(id, is_active) {
  return request.post(`/subscriptions/${id}/toggle`, { is_active })
}

export function runSubscription(id) {
  return request.post(`/subscriptions/${id}/run`)
}

export function getExecutions(id, params) {
  return request.get(`/subscriptions/${id}/executions`, { params })
}

export function getNextRunTime(cron) {
  return request.get(`/subscriptions/cron/next/${encodeURIComponent(cron)}`)
}
