import request from "@/utils/request"

export interface TemplateShareInfo {
  id: number
  template_id: number
  shared_by: number
  user_id: number
  username: string
  created_at: string
}

export function shareTemplate(id: number, data: { user_ids: number[] }): Promise<void> {
  return request({ url: `/templates/${id}/share`, method: "post", data }) as Promise<void>
}

export function unshareTemplate(templateId: number, userId: number): Promise<void> {
  return request({ url: `/templates/${templateId}/share/${userId}`, method: "delete" }) as Promise<void>
}

export function getSharedTemplates(): Promise<TemplateShareInfo[]> {
  return request({ url: "/templates/shared", method: "get" }) as Promise<TemplateShareInfo[]>
}

export function getTemplateShares(templateId: number): Promise<TemplateShareInfo[]> {
  return request({ url: `/templates/${templateId}/shares`, method: "get" }) as Promise<TemplateShareInfo[]>
}
