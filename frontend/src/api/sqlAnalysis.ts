import request from "@/utils/request"

export interface SqlAnalysis {
  id: number
  sql: string
  table_name?: string
  estimated_rows?: number
  complexity?: string
  suggestions: string[]
}

export function analyzeSql(data: { sql: string; data_source_id: number }): Promise<SqlAnalysis> {
  return request({ url: "/sql/analyze", method: "post", data }) as Promise<SqlAnalysis>
}

// Legacy alias
export const analyzeSQL = analyzeSql
