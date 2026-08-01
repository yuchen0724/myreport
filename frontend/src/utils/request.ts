import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios"
import { ElMessage } from "element-plus"
import { useUserStore } from "@/store"
import type { ApiError } from "@/types/api"

/** Extended Axios instance with typed response helpers */
const request: AxiosInstance = axios.create({
  baseURL: "/api",
  timeout: 180000,  // 3 minutes, supports NL2SQL long requests
})

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const userStore = useUserStore()
    if (userStore.token && config.headers) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    if (response.status === 204) {
      return { success: true } as unknown as Record<string, unknown>
    }
    return response.data
  },
  (error: AxiosError<ApiError>) => {
    if (error.response) {
      const { status, data } = error.response

      // 401 Unauthorized: clear token and redirect
      if (status === 401) {
        const userStore = useUserStore()
        userStore.logout()
        // 清理旧版本遗留的 localStorage token，避免失效 token 被迁移回 sessionStorage
        // 后触发“401 -> 登录页 -> 恢复旧 token -> 401”的整页刷新循环。
        try {
          window.localStorage.removeItem("token")
          window.localStorage.removeItem("user")
        } catch {
          // 某些隐私模式可能禁止访问 localStorage，sessionStorage 仍已清理。
        }
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }

      // 429 Rate limited: warn without retry
      if (status === 429) {
        if (window.location.pathname !== '/login') {
          ElMessage.warning('请求过于频繁请稍后再试')
        }
        return Promise.reject(error)
      }

      // Other errors
      if (window.location.pathname !== '/login') {
        const msg = data?.message || data?.detail || "请求失败"
        ElMessage.error(msg)
      }
    } else {
      if (window.location.pathname !== '/login') {
        ElMessage.error("网络错误")
      }
    }
    return Promise.reject(error)
  }
)

export default request
