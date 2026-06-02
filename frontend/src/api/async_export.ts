import request from "@/utils/request"

export interface AsyncExportTask {
  id: string
  status: string
  progress: number
  file_url?: string
  created_at: string
}

export function createExport(data: { data_source_id: number; sql: string; format: string }): Promise<AsyncExportTask> {
  return request({ url: "/async-export", method: "post", data }) as Promise<AsyncExportTask>
}

export function getExportStatus(taskId: string): Promise<AsyncExportTask> {
  return request({ url: `/async-export/${taskId}`, method: "get" }) as Promise<AsyncExportTask>
}

export function cancelExport(taskId: string): Promise<void> {
  return request({ url: `/async-export/${taskId}/cancel`, method: "post" }) as Promise<void>
}

// ── Legacy name aliases ───────────────────────────────────
export const createExportTask = createExport
export const getTaskStatus = getExportStatus
export function getUserTasks(): Promise<AsyncExportTask[]> {
  return request({ url: "/async-export", method: "get" }) as Promise<AsyncExportTask[]>
}
export function downloadExportFile(taskId: string): Promise<Blob> {
  return request({ url: `/async-export/${taskId}/download`, method: "get", responseType: "blob" }) as Promise<Blob>
}
