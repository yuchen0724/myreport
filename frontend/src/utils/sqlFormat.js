// frontend/src/utils/sqlFormat.js
// SQL 格式化工具，使用 sql-formatter 库
import { format } from 'sql-formatter'

/**
 * 格式化 SQL 语句
 * @param {string} sql - 原始 SQL 语句
 * @param {string} language - 数据库方言，默认 auto（自动识别）
 * @returns {string} 格式化后的 SQL
 */
export function formatSQL(sql, language = 'doris') {
  if (!sql || typeof sql !== 'string') {
    return sql || ''
  }

  try {
    return format(sql, {
      language: language,
      tabWidth: 2,
      keywordCase: 'upper',
      linesBetweenQueries: 2
    })
  } catch (e) {
    console.warn('[SQL Format] 格式化失败，返回原始SQL:', e.message)
    return sql
  }
}
