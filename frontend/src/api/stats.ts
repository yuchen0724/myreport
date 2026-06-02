import request from "@/utils/request"

export interface SystemStats {
  total_queries: number
  total_templates: number
  total_data_sources: number
  active_users: number
}

export function getSystemStats(): Promise<SystemStats> {
  return request({ url: "/stats", method: "get" }) as Promise<SystemStats>
}
