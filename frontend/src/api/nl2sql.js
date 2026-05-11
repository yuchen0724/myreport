// frontend/src/api/nl2sql.js
import request from "@/utils/request"

// 缓存前端配置
let frontendConfig = null
let configLoaded = false

/**
 * 获取前端配置（包含 NL2SQL 超时时间）
 * 动态跟随后端配置，超时时间 = 后端超时 + 60秒缓冲
 */
export async function getFrontendConfig() {
  if (configLoaded && frontendConfig) {
    return frontendConfig
  }
  
  try {
    // 直接用 fetch 调用配置接口，绕过认证
    const token = localStorage.getItem('token')
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
    
    const response = await fetch('/api/config', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers
      }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    
    const data = await response.json()
    frontendConfig = data
    configLoaded = true
    
    console.log('[NL2SQL] 📋 获取前端配置成功:', {
      nl2sql_timeout: data.nl2sql_timeout,
      nl2sql_timeout_ms: data.nl2sql_timeout_ms
    })
    
    return data
  } catch (error) {
    console.warn('[NL2SQL] ⚠️ 获取前端配置失败，使用默认值:', error.message)
    // 返回默认值：后端 300s + 60s 缓冲 = 360s
    return {
      nl2sql_timeout: 300,
      nl2sql_timeout_ms: 360000
    }
  }
}

/**
 * 获取 NL2SQL 请求的超时时间（毫秒）
 * 动态跟随后端配置
 */
export async function getNL2SQLTimeout() {
  const config = await getFrontendConfig()
  return config.nl2sql_timeout_ms
}

export function parseQuestion(data) {
  const requestId = `nl2sql_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  const startTime = performance.now()
  
  console.group(`[NL2SQL] 📤 请求发送 | ${requestId}`)
  console.log('├─ 请求参数:', JSON.stringify(data, null, 2))
  console.log('├─ 数据源ID:', data.data_source_id)
  console.log('├─ 问题:', data.question)
  console.log('├─ 发起时间:', new Date().toISOString())
  console.groupEnd()

  // 动态获取超时时间
  return getNL2SQLTimeout().then(timeout => {
    console.log(`[NL2SQL] ⏱️ 请求超时时间: ${timeout}ms (${timeout/1000}s)`)
    
    return request({
      url: "/nl2sql/parse",
      method: "post",
      data,
      timeout: timeout
    })
  })
    .then(response => {
      const endTime = performance.now()
      const duration = (endTime - startTime).toFixed(2)
      
      console.group(`[NL2SQL] 📥 请求成功 | ${requestId}`)
      console.log('├─ 耗时:', `${duration}ms`)
      console.log('├─ 执行时间:', `${response.execution_time_ms}ms`)
      console.log('├─ SQL建议数量:', response.suggestions?.length || 0)
      console.log('├─ 选中的SQL:', response.selected_sql)
      console.log('├─ 查询结果列数:', response.query_result?.columns?.length || 0)
      console.log('├─ 查询结果行数:', response.query_result?.total || 0)
      console.log('└─ 完整响应:', response)
      console.groupEnd()
      
      return response
    })
    .catch(error => {
      const endTime = performance.now()
      const duration = (endTime - startTime).toFixed(2)
      
      console.group(`[NL2SQL] ❌ 请求失败 | ${requestId}`)
      console.log('├─ 耗时:', `${duration}ms`)
      console.log('├─ 错误信息:', error.message || error)
      console.log('├─ 错误响应:', error.response?.data)
      console.log('└─ HTTP状态码:', error.response?.status)
      console.groupEnd()
      
      throw error
    })
}