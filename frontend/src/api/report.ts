import request from "@/utils/request"

export function exportReport(data: { template_id: number; format: string; params?: Record<string, unknown> }): Promise<Blob> {
  return request({
    url: "/report/export",
    method: "post",
    data,
    responseType: "blob",
  }) as Promise<Blob>
}

export function previewReport(data: { template_id: number; params?: Record<string, unknown> }): Promise<Record<string, unknown>> {
  return request({ url: "/report/preview", method: "post", data }) as Promise<Record<string, unknown>>
}

// ── Legacy name aliases ───────────────────────────────────
export function exportExcel(data: { template_id: number; params?: Record<string, unknown> }): Promise<Blob> {
  return exportReport({ ...data, format: "xlsx" })
}
export function exportPDF(data: { template_id: number; params?: Record<string, unknown> }): Promise<Blob> {
  return exportReport({ ...data, format: "pdf" })
}

// ── Async export (for ReportView) ─────────────────────────
export function exportExcelAsync(data: { template_id: number; params?: Record<string, unknown> }): Promise<{ task_id: string }> {
  return request({ url: "/report/export-async", method: "post", data }) as Promise<{ task_id: string }>
}
export function getExportTask(taskId: string): Promise<{ status: string; progress?: number }> {
  return request({ url: `/async-export/${taskId}`, method: "get" }) as Promise<{ status: string; progress?: number }>
}
export function downloadExportFile(taskId: string): Promise<Blob> {
  return request({ url: `/async-export/${taskId}/download`, method: "get", responseType: "blob" }) as Promise<Blob>
}
