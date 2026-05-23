// frontend/src/api/sqlAnalysis.js
import request from "@/utils/request"

/**
 * 分析 SQL 复杂度
 * @param {string} sql - SQL 语句
 * @param {boolean} save - 是否保存到数据库
 */
export function analyzeSQL(sql, save = false) {
  return request.post('/sql/analyze', { sql, save })
}

/**
 * 根据 sql_hash 获取缓存的分析结果
 */
export function getAnalysisByHash(sqlHash) {
  return request.get(`/sql/analyze/${sqlHash}`)
}

/**
 * 获取 SQL 分析历史记录
 */
export function getAnalysisHistory(params) {
  return request.get('/sql/history', { params })
}

/**
 * 获取 SQL 分析统计数据
 */
export function getAnalysisStats() {
  return request.get('/sql/stats')
}
