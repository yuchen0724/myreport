import request from "@/utils/request"

export interface ChartData {
  columns: string[]
  rows: unknown[][]
  chart_type?: string
}

export interface ChartRequest {
  data_source_id: number
  sql: string
  chart_type?: string
  x_axis?: string
  y_axis?: string
}

export function generateChart(data: ChartRequest): Promise<ChartData> {
  return request({ url: "/charts/generate", method: "post", data }) as Promise<ChartData>
}
