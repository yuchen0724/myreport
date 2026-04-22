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

export function shareTemplate(id, data) {
  return request({
    url: `/templates/${id}/share`,
    method: "post",
    data
  })
}
