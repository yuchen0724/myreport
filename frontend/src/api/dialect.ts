import request from "@/utils/request"

export interface DialectInfo {
  id: number
  name: string
  description: string
  functions: string[]
  keywords: string[]
}

export function getDialects(): Promise<DialectInfo[]> {
  return request({ url: "/dialects", method: "get" }) as Promise<DialectInfo[]>
}

export function getDialect(id: number): Promise<DialectInfo> {
  return request({ url: `/dialects/${id}`, method: "get" }) as Promise<DialectInfo>
}

// Legacy alias
export const getDialectDetail = getDialect
