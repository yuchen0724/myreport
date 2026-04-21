// frontend/src/api/template.js
import request from "@/utils/request"

export function getTemplateList(params) {
  return request({
    url: "/templates",
    method: "get",
    params
  })
}

export function getTemplate(id) {
  return request({
    url: `/templates/${id}`,
    method: "get"
  })
}

export function createTemplate(data) {
  return request({
    url: "/templates",
    method: "post",
    data
  })
}

export function updateTemplate(id, data) {
  return request({
    url: `/templates/${id}`,
    method: "put",
    data
  })
}

export function deleteTemplate(id) {
  return request({
    url: `/templates/${id}`,
    method: "delete"
  })
}

export function getTemplateVersions(id) {
  return request({
    url: `/templates/${id}/versions`,
    method: "get"
  })
}

export function rollbackTemplate(id, version) {
  return request({
    url: `/templates/${id}/rollback/${version}`,
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
