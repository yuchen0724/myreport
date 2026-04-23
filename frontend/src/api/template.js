// frontend/src/api/template.js
import request from "@/utils/request"

export function getTemplateList(params) {
  return request({
    url: "/api/templates",
    method: "get",
    params
  })
}

export function getTemplate(id) {
  return request({
    url: `/api/templates/${id}`,
    method: "get"
  })
}

export function createTemplate(data) {
  return request({
    url: "/api/templates",
    method: "post",
    data
  })
}

export function updateTemplate(id, data) {
  return request({
    url: `/api/templates/${id}`,
    method: "put",
    data
  })
}

export function deleteTemplate(id) {
  return request({
    url: `/api/templates/${id}`,
    method: "delete"
  })
}

export function getTemplateVersions(id) {
  return request({
    url: `/api/templates/${id}/versions`,
    method: "get"
  })
}

export function rollbackTemplate(id, version) {
  return request({
    url: `/api/templates/${id}/rollback/${version}`,
    method: "post"
  })
}

/**
 * 获取版本差异
 * @param {number} templateId - 模板 ID
 * @param {number} version1 - 版本 1
 * @param {number} version2 - 版本 2
 */
export function getVersionDiff(templateId, version1, version2) {
  return request({
    url: `/api/templates/${templateId}/versions/diff`,
    method: "get",
    params: { version1, version2 }
  })
}

export function shareTemplate(id, data) {
  return request({
    url: `/api/templates/${id}/share`,
    method: "post",
    data
  })
}
