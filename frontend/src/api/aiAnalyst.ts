import request from "@/utils/request"

export interface AiAnalysisRequest {
  data_source_id: number
  question: string
  context?: string
}

export interface AiAnalysisResponse {
  answer: string
  sql?: string
  chart_config?: Record<string, unknown>
}

export function askAi(data: AiAnalysisRequest): Promise<AiAnalysisResponse> {
  return request({ url: "/ai-analyst/ask", method: "post", data }) as Promise<AiAnalysisResponse>
}

export function getAiHistory(): Promise<AiAnalysisResponse[]> {
  return request({ url: "/ai-analyst/history", method: "get" }) as Promise<AiAnalysisResponse[]>
}

// Legacy alias (streaming chat not yet implemented)
export function chatStream(_data: AiAnalysisRequest): Promise<AiAnalysisResponse> {
  return askAi(_data)
}
