// frontend/src/api/sqlReviews.js
import request from '@/utils/request'

/**
 * 获取审核列表
 * @param {Object} params - { status, submitted_by, page, page_size }
 */
export function listReviews(params = {}) {
  return request.get('/api/reviews', { params })
}

/**
 * 获取审核详情
 * @param {number} id - 审核工单 ID
 */
export function getReview(id) {
  return request.get(`/api/reviews/${id}`)
}

/**
 * 提交审核工单
 * @param {Object} data - { template_id, sql_content }
 */
export function createReview(data) {
  return request.post('/api/reviews', data)
}

/**
 * 审核操作（通过/拒绝）
 * @param {number} id - 审核工单 ID
 * @param {Object} data - { status: 'approved'|'rejected', review_comment }
 */
export function reviewSql(id, data) {
  return request.put(`/api/reviews/${id}/review`, data)
}

/**
 * 删除审核工单
 * @param {number} id - 审核工单 ID
 */
export function deleteReview(id) {
  return request.delete(`/api/reviews/${id}`)
}
