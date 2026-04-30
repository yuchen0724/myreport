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
      if (status === 401) {
        const userStore = useUserStore()
        userStore.logout()
        window.location.href = "/login"
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
