import request from "@/utils/request"

/**
 * 获取所有支持的 SQL 方言列表
 */
export function getDialects() {
  return request({
    url: "/dialects",
    method: "get"
  })
}

/**
 * 获取指定方言的详细信息
 */
export function getDialectDetail(name) {
  return request({
    url: `/dialects/${name}`,
    method: "get"
  })
}

/**
 * 获取方言允许的关键字和函数列表
 */
export function getDialectKeywords(name) {
  return request({
    url: `/dialects/${name}/keywords`,
    method: "get"
  })
}

/**
 * 方言感知的 SQL 验证
 */
export function validateSQLWithDialect(data) {
  return request({
    url: "/dialects/validate",
    method: "post",
    data
  })
}
