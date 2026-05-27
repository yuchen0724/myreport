// frontend/src/api/aiAnalyst.js
import request from "@/utils/request"

/**
 * AI 数据分析师 - 同步对话
 * @param {Object} data - { message, data_source_id, conversation_id?, group_id? }
 */
export function chat(data) {
  return request({
    url: "/ai-analyst/chat",
    method: "post",
    data,
    timeout: 300000, // 5分钟
  })
}

/**
 * AI 数据分析师 - 流式对话 (SSE)
 * @param {Object} data - { message, data_source_id, conversation_id?, group_id? }
 * @param {Function} onToken - 收到文本片段回调
 * @param {Function} onToolCall - 工具调用回调
 * @param {Function} onToolResult - 工具结果回调
 * @param {Function} onChart - 图表配置回调
 * @param {Function} onDone - 完成回调
 * @param {Function} onError - 错误回调
 * @returns {EventSource} - 可用于手动关闭
 */
export function chatStream(
  data,
  { onToken, onToolCall, onToolResult, onChart, onDone, onError }
) {
  // 使用 fetch + ReadableStream 替代 EventSource（因为 EventSource 不支持 POST）
  const abortController = new AbortController()

  const token = sessionStorage.getItem("token")
  const headers = {
    "Content-Type": "application/json",
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  fetch("/api/ai-analyst/chat/stream", {
    method: "POST",
    headers,
    body: JSON.stringify(data),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        onError && onError(errorData.detail || `HTTP ${response.status}`)
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() // 保留不完整的行

        let eventType = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.substring(7).trim()
          } else if (line.startsWith("data: ")) {
            const rawData = line.substring(6)
            try {
              const parsed = JSON.parse(rawData)
              switch (eventType) {
                case "token":
                  onToken && onToken(parsed.content || "")
                  break
                case "tool_call":
                  onToolCall && onToolCall(parsed)
                  break
                case "tool_result":
                  onToolResult && onToolResult(parsed)
                  break
                case "chart":
                  onChart && onChart(parsed.chart_config)
                  break
                case "done":
                  onDone && onDone(parsed)
                  break
                case "error":
                  onError && onError(parsed.error || "未知错误")
                  break
              }
            } catch (e) {
              // 非 JSON 数据，忽略
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError && onError(err.message || "网络错误")
      }
    })

  // 返回 abort 函数
  return { abort: () => abortController.abort() }
}

/**
 * 获取数据库表结构
 * @param {number} dataSourceId - 数据源 ID
 * @param {string} tableName - 指定表名（可选）
 */
export function getSchema(dataSourceId, tableName = null) {
  const params = { data_source_id: dataSourceId }
  if (tableName) params.table_name = tableName

  return request({
    url: "/ai-analyst/schema",
    method: "get",
    params,
    timeout: 60000,
  })
}
