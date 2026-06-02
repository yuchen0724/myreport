import request from "@/utils/request"

export interface TemplateVersion {
  id: number
  template_id: number
  version: number
  config: Record<string, unknown>
  created_by: number
  created_at: string
}

export function getTemplateVersions(templateId: number): Promise<TemplateVersion[]> {
  return request({ url: `/templates/${templateId}/versions`, method: "get" }) as Promise<TemplateVersion[]>
}

export function rollbackVersion(templateId: number, version: number): Promise<void> {
  return request({ url: `/templates/${templateId}/rollback/${version}`, method: "post" }) as Promise<void>
}

// ── Legacy aliases ────────────────────────────────────────
export const getVersionDiff = getTemplateVersions
