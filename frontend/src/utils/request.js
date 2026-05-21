import axios from "axios"
import { ElMessage } from "element-plus"
import { useUserStore } from "@/store"

const request = axios.create({
  baseURL: "/api",
  timeout: 180000  // 3分钟，支持 NL2SQL 长时间请求
})

request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    if (response.status === 204) {
      return { success: true }
    }
    return response.data
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response

      // 401 未授权：清除 token
      if (status === 401) {
        const userStore = useUserStore()
        userStore.logout()
        // 只有不在登录页时才跳转
        if (!window.location.pathname.includes('/login')) {
          // 使用硬跳转以确保 Pinia 状态完全重置
          // （router.push 可能因循环依赖无法在此文件使用）
          window.location.href = '/login'
        }
      }
      
      // 429 限流：提示但不重试
      if (status === 429) {
        // 登录页不显示限流提示，避免干扰
        if (!window.location.pathname.includes('/login')) {
          ElMessage.warning('请求过于频繁请稍后再试')
        }
        return Promise.reject(error)
      }
      
      // 登录页不显示其他错误提示
      if (!window.location.pathname.includes('/login')) {
        ElMessage.error(data.message || data.detail || "请求失败")
      }
    } else {
      if (!window.location.pathname.includes('/login')) {
        ElMessage.error("网络错误")
      }
    }
    return Promise.reject(error)
  }
)

export default request
