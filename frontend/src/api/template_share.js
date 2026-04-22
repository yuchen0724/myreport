// frontend/src/api/template_share.js
import request from "@/utils/request"

export function shareTemplate(templateId, data) {
  return request({
    url: `/templates/${templateId}/share`,
    method: "post",
    data
  })
}

export function getSharedTemplates(params) {
  return request({
    url: "/templates/shared/me",
    method: "get",
    params
  })
}

export function getTemplateShares(templateId) {
  return request({
    url: `/templates/${templateId}/shares`,
    method: "get"
  })
}
