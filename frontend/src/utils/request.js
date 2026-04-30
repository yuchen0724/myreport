import axios from "axios"
import { ElMessage } from "element-plus"
import { useUserStore } from "@/store"

const request = axios.create({
  baseURL: "/api",
  timeout: 30000
})

request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
      console.log('Request:', config.method, config.url, 'Token:', userStore.token.substring(0, 20) + '...')
    } else {
      console.log('Request:', config.method, config.url, 'NO TOKEN')
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
      console.error('API Error:', status, data)
      
      // 401 未授权：不弹窗，不重试，静默处理
      if (status === 401) {
        console.warn('未登录，跳过错误提示')
        // 不调用 ElMessage，避免频繁弹窗
        return Promise.reject(new Error('Unauthorized'))
      }
      
      // 429 限流：提示但不重试
      if (status === 429) {
        ElMessage.warning('请求过于频繁，请稍后再试')
        return Promise.reject(error)
      }
      
      ElMessage.error(data.message || data.detail || "请求失败")
    } else {
      console.error('Network Error:', error)
      ElMessage.error("网络错误")
    }
    return Promise.reject(error)
  }
)

export default request
