import request from "@/utils/request"
import type { PaginatedResponse } from "@/types/api"

export interface TemplateConfig {
  data_source_id: number
  sql: string
  [key: string]: unknown
}

export interface Template {
  id: number
  name: string
  description: string
  config: TemplateConfig
  version: number
  is_public: boolean
  created_by: number
  created_at: string
  updated_at: string
}

export interface TemplateCreate {
  name: string
  description?: string
  config: TemplateConfig
  is_public?: boolean
}

export interface TemplateUpdate {
  name?: string
  description?: string
  config?: TemplateConfig
  is_public?: boolean
}

export interface TemplateVersion {
  id: number
  template_id: number
  version: number
  config: TemplateConfig
  created_by: number
  created_at: string
}

export function getTemplateList(params?: {
  page?: number
  page_size?: number
  user_id?: number
}): Promise<Template[] | PaginatedResponse<Template>> {
  return request({
    url: "/templates",
    method: "get",
    params
  }) as Promise<Template[] | PaginatedResponse<Template>>
}

export function getTemplate(id: number): Promise<Template> {
  return request({
    url: `/templates/${id}`,
    method: "get"
  }) as Promise<Template>
}

export function createTemplate(data: TemplateCreate): Promise<Template> {
  return request({
    url: "/templates",
    method: "post",
    data
  }) as Promise<Template>
}

export function updateTemplate(id: number, data: TemplateUpdate): Promise<Template> {
  return request({
    url: `/templates/${id}`,
    method: "put",
    data
  }) as Promise<Template>
}

export function deleteTemplate(id: number): Promise<void> {
  return request({
    url: `/templates/${id}`,
    method: "delete"
  }) as Promise<void>
}

export function getTemplateVersions(id: number): Promise<TemplateVersion[]> {
  return request({
    url: `/templates/${id}/versions`,
    method: "get"
  }) as Promise<TemplateVersion[]>
}

export function rollbackTemplate(id: number, version: number): Promise<Template> {
  return request({
    url: `/templates/${id}/rollback/${version}`,
    method: "post"
  }) as Promise<Template>
}

export function getVersionDiff(
  templateId: number,
  version1: number,
  version2: number
): Promise<{
  version1: { version: number; config: TemplateConfig; created_at: string }
  version2: { version: number; config: TemplateConfig; created_at: string }
  changes: { added: string[]; removed: string[]; modified: Array<{ key: string; old: unknown; new: unknown }> }
}> {
  return request({
    url: `/templates/${templateId}/versions/diff`,
    method: "get",
    params: { version1, version2 }
  }) as Promise<{
    version1: { version: number; config: TemplateConfig; created_at: string }
    version2: { version: number; config: TemplateConfig; created_at: string }
    changes: { added: string[]; removed: string[]; modified: Array<{ key: string; old: unknown; new: unknown }> }
  }>
}

export function shareTemplate(id: number, data: { user_ids: number[] }): Promise<void> {
  return request({
    url: `/templates/${id}/share`,
    method: "post",
    data
  }) as Promise<void>
}
