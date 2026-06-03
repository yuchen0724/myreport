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

export interface StreamCallbacks {
  onToken?: (content: string) => void
  onToolCall?: (data: { tool_name: string; tool_input: Record<string, unknown> }) => void
  onToolResult?: (data: { tool_name: string; tool_output: string }) => void
  onChart?: (config: Record<string, unknown>) => void
  onDone?: (data: { conversation_id: string }) => void
  onError?: (error: string) => void
}

export interface StreamRef {
  abort: () => void
}

/** SSE 流式聊天 — 基于 fetch + ReadableStream */
export function chatStream(
  data: {
    message: string
    data_source_id: number
    conversation_id?: string | null
    group_id?: number | null
  },
  callbacks: StreamCallbacks
): StreamRef {
  const controller = new AbortController()
  const baseUrl = "/api/ai-analyst/chat/stream"

  const body = JSON.stringify({
    message: data.message,
    data_source_id: data.data_source_id,
    conversation_id: data.conversation_id || undefined,
    group_id: data.group_id || undefined,
  })

  // 从 sessionStorage 读取 token（Pinia store 在模块作用域不可用）
  const token = window.sessionStorage.getItem("token")
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (token) headers["Authorization"] = `Bearer ${token}`

  fetch(baseUrl, {
    method: "POST",
    headers,
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errText = await response.text().catch(() => "Unknown error")
        callbacks.onError?.(`HTTP ${response.status}: ${errText}`)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        callbacks.onError?.("Response body not readable")
        return
      }

      const decoder = new TextDecoder()
      let buffer = ""

      /** 异步事件队列：逐事件处理，给 Vue 时间渲染 DOM */
      async function processEvents(events: Array<Record<string, unknown>>) {
        for (const event of events) {
          switch (event.type) {
            case "token":
              callbacks.onToken?.(event.content as string)
              break
            case "tool_call":
              callbacks.onToolCall?.({
                tool_name: event.tool_name as string,
                tool_input: (event.tool_input as Record<string, unknown>) || {},
              })
              break
            case "tool_result":
              callbacks.onToolResult?.({
                tool_name: event.tool_name as string,
                tool_output: (event.tool_output as string) || "",
              })
              break
            case "chart":
              callbacks.onChart?.(event.chart_config as Record<string, unknown>)
              break
            case "done":
              callbacks.onDone?.({ conversation_id: event.conversation_id as string })
              break
            case "error":
              callbacks.onError?.((event.error as string) || "Unknown error")
              break
          }
          // 每个事件之间 yield 给 Vue render cycle
          await new Promise((r) => setTimeout(r, 0))
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        const events: Array<Record<string, unknown>> = []
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              events.push(JSON.parse(line.slice(6)))
            } catch {
              // skip malformed SSE lines
            }
          }
        }
        if (events.length > 0) {
          await processEvents(events)
        }
      }
    })
    .catch((err) => {
      if (err.name === "AbortError") return
      callbacks.onError?.(err.message || "Network error")
    })

  return { abort: () => controller.abort() }
}

// ── Synchronous API (non-streaming) ─────────────────────

export function askAi(data: AiAnalysisRequest): Promise<AiAnalysisResponse> {
  return request({ url: "/ai-analyst/ask", method: "post", data }) as Promise<AiAnalysisResponse>
}

export function getAiHistory(): Promise<AiAnalysisResponse[]> {
  return request({ url: "/ai-analyst/history", method: "get" }) as Promise<AiAnalysisResponse[]>
}
