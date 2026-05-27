import request from "@/utils/request"

/**
 * 获取指定数据源的连接池指标
 * @param {number} dataSourceId 数据源ID
 * @returns {Promise} 连接池指标
 */
export function getPoolMetrics(dataSourceId) {
  return request({
    url: `/metrics/pool/${dataSourceId}`,
    method: "get",
  })
}

/**
 * 获取所有数据源的连接池指标
 * @returns {Promise} 所有连接池指标
 */
export function getAllPoolMetrics() {
  return request({
    url: "/metrics/pool",
    method: "get",
  })
}
