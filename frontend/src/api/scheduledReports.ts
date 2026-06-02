import request from "@/utils/request"

export interface ScheduledReport {
  id: number
  name: string
  template_id: number
  cron_expression: string
  format: string
  recipients: string[]
  is_active: boolean
  last_run_at?: string
  created_at: string
}

export const listReports = getScheduledReports
export function getScheduledReports(): Promise<ScheduledReport[]> {
  return request({ url: "/scheduled-reports", method: "get" }) as Promise<ScheduledReport[]>
}

export function createScheduledReport(data: Partial<ScheduledReport>): Promise<ScheduledReport> {
  return request({ url: "/scheduled-reports", method: "post", data }) as Promise<ScheduledReport>
}

export function updateScheduledReport(id: number, data: Partial<ScheduledReport>): Promise<ScheduledReport> {
  return request({ url: `/scheduled-reports/${id}`, method: "put", data }) as Promise<ScheduledReport>
}

export function deleteScheduledReport(id: number): Promise<void> {
  return request({ url: `/scheduled-reports/${id}`, method: "delete" }) as Promise<void>
}

export function getNextRunTime(cronExpression: string): Promise<{ next_run: string }> {
  return request({ url: "/scheduled-reports/next-run", method: "post", data: { cron_expression: cronExpression } }) as Promise<{ next_run: string }>
}

// ── Legacy name aliases ───────────────────────────────────
export const createReport = createScheduledReport
export const updateReport = updateScheduledReport
export const deleteReport = deleteScheduledReport
export function toggleReport(id: number, is_active: boolean): Promise<void> {
  return updateScheduledReport(id, { is_active } as Partial<ScheduledReport>)
}
export function runNow(id: number): Promise<void> {
  return request({ url: `/scheduled-reports/${id}/run-now`, method: "post" }) as Promise<void>
}
export function getDeliveries(reportId: number): Promise<Record<string, unknown>[]> {
  return request({ url: `/scheduled-reports/${reportId}/deliveries`, method: "get" }) as Promise<Record<string, unknown>[]>
}
