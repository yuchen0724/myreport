import request from "@/utils/request"

export interface UserProfile {
  id: number
  username: string
  email: string
  role_id: number
  is_active: boolean
  created_at: string
}

export function getUserList(params?: Record<string, unknown>): Promise<UserProfile[]> {
  return request({ url: "/users", method: "get", params }) as Promise<UserProfile[]>
}

export function getUser(id: number): Promise<UserProfile> {
  return request({ url: `/users/${id}`, method: "get" }) as Promise<UserProfile>
}

export function createUser(data: { username: string; email: string; password: string; role_id?: number }): Promise<UserProfile> {
  return request({ url: "/users", method: "post", data }) as Promise<UserProfile>
}

export function updateUser(id: number, data: Partial<UserProfile>): Promise<UserProfile> {
  return request({ url: `/users/${id}`, method: "put", data }) as Promise<UserProfile>
}

export function deleteUser(id: number): Promise<void> {
  return request({ url: `/users/${id}`, method: "delete" }) as Promise<void>
}
