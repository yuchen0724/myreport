import request from "@/utils/request"

export function generateReportDraft(data: {
  data_source_id: number
  requirement: string
  preferred_chart?: string
}): Promise<Record<string, any>> {
  return request({ url: "/ai-design/report-draft", method: "post", data }) as Promise<Record<string, any>>
}

export function auditMetrics(dataSourceId: number): Promise<Record<string, any>> {
  return request({ url: `/ai-design/metric-audit/${dataSourceId}`, method: "get" }) as Promise<Record<string, any>>
}

export function generateMetricDraft(data: {
  data_source_id: number
  requirement: string
}): Promise<Record<string, any>> {
  return request({ url: "/ai-design/metric-draft", method: "post", data }) as Promise<Record<string, any>>
}
