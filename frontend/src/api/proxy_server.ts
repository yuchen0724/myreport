import request from "@/utils/request"

export interface ProxyServer {
  id: number
  host: string
  port: number
  proxy_type: string
  username?: string
  is_active: boolean
  created_by: number
  created_at: string
}

export function getProxyList(): Promise<ProxyServer[]> {
  return request({ url: "/proxy-servers", method: "get" }) as Promise<ProxyServer[]>
}

export function getProxy(id: number): Promise<ProxyServer> {
  return request({ url: `/proxy-servers/${id}`, method: "get" }) as Promise<ProxyServer>
}

export function createProxy(data: Partial<ProxyServer> & { password?: string }): Promise<ProxyServer> {
  return request({ url: "/proxy-servers", method: "post", data }) as Promise<ProxyServer>
}

export function updateProxy(id: number, data: Partial<ProxyServer> & { password?: string }): Promise<ProxyServer> {
  return request({ url: `/proxy-servers/${id}`, method: "put", data }) as Promise<ProxyServer>
}

export function deleteProxy(id: number): Promise<void> {
  return request({ url: `/proxy-servers/${id}`, method: "delete" }) as Promise<void>
}

// ── Legacy name aliases ───────────────────────────────────
export const getProxyServer = getProxy
export const getProxyServerList = getProxyList
export const createProxyServer = createProxy
export const updateProxyServer = updateProxy
export const deleteProxyServer = deleteProxy
export function getActiveProxyServers(): Promise<ProxyServer[]> {
  return request({ url: "/proxy-servers/active", method: "get" }) as Promise<ProxyServer[]>
}
export function testProxyServer(data: { host: string; port: number }): Promise<{ success: boolean; message: string }> {
  return request({ url: "/proxy-servers/test", method: "post", data }) as Promise<{ success: boolean; message: string }>
}
