import request from "@/utils/request"

export interface PoolMetrics {
  active_connections: number
  idle_connections: number
  total_connections: number
  wait_count: number
  wait_time_ms: number
}

export function getPoolMetrics(): Promise<PoolMetrics> {
  return request({ url: "/pool-metrics", method: "get" }) as Promise<PoolMetrics>
}

// Legacy alias
export const getAllPoolMetrics = getPoolMetrics
