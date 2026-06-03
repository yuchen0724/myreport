import request from "@/utils/request"

export interface LoginRequest {
  username: string
  password: string
}

export interface User {
  id: number
  username: string
  email: string
  role_id: number
  is_active: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user?: User
}

export function login(username: string, password: string): Promise<LoginResponse> {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  return request({
    url: "/auth/login",
    method: "post",
    data: formData,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    }
  }) as Promise<LoginResponse>
}

export function getCurrentUser(): Promise<User> {
  return request({
    url: "/auth/me",
    method: "get"
  }) as Promise<User>
}
