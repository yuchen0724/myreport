// frontend/src/api/template_share.js
import request from "@/utils/request"

/**
 * 获取模板列表
 */
export function getTemplates(params = {}) {
  return request({
    url: "/api/templates",
    method: "get",
    params
  })
}

/**
 * 分享模板
 * @param {number} templateId - 模板 ID
 * @param {Array<number>} userIds - 用户 ID 列表
 */
export function shareTemplate(templateId, userIds) {
  return request({
    url: `/api/templates/${templateId}/share`,
    method: "post",
    data: userIds
  })
}

/**
 * 获取分享给我的模板列表
 */
export function getSharedTemplates(params = {}) {
  return request({
    url: "/api/templates/shared/me",
    method: "get",
    params
  })
}

/**
 * 获取模板的分享用户列表
 * @param {number} templateId - 模板 ID
 */
export function getTemplateShares(templateId) {
  return request({
    url: `/api/templates/${templateId}/shares`,
    method: "get"
  })
}

/**
 * 取消分享模板
 * @param {number} templateId - 模板 ID
 * @param {number} userId - 用户 ID
 */
export function unshareTemplate(templateId, userId) {
  return request({
    url: `/api/templates/${templateId}/unshare`,
    method: "post",
    data: { user_id: userId }
  })
}
