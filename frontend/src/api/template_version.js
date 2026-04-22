// frontend/src/api/template_version.js
import request from "@/utils/request"

export function getTemplateVersions(templateId) {
  return request({
    url: `/templates/${templateId}/versions`,
    method: "get"
  })
}

export function rollbackTemplate(templateId, version) {
  return request({
    url: `/templates/${templateId}/rollback/${version}`,
    method: "post"
  })
}

export function getVersionDiff(templateId, version1, version2) {
  return request({
    url: `/templates/${templateId}/versions/diff`,
    method: "get",
    params: {
      version1,
      version2
    }
  })
}
