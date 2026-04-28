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
      if (status === 401) {
        const userStore = useUserStore()
        userStore.logout()
        window.location.href = "/login"
      }
      ElMessage.error(data.message || data.detail || "请求失败")
    } else {
      ElMessage.error("网络错误")
    }
    return Promise.reject(error)
  }
)

export default request
