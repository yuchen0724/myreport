// frontend/src/api/modelCompare.js
import request from "@/utils/request"

export function startCompare(data) {
  return request.post('/model-compare/compare', data)
}

export function getCompareStatus(compareId) {
  return request.get(`/model-compare/compare/${compareId}`)
}

export function deleteCompare(compareId) {
  return request.delete(`/model-compare/compare/${compareId}`)
}
