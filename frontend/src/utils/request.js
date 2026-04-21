import axios from "axios"
import { ElMessage } from "element-plus"
import { useUserStore } from "@/store"

const request = axios.create({
  baseURL: "/api",
  timeout: 30000
})

request.interceptors.request.use(
  (config) => {
    console.log('请求拦截器:', config)
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    console.log('响应拦截器:', response)
    return response.data
  },
  (error) => {
    console.error('响应错误:', error)
    if (error.response) {
      const { status, data } = error.response
      console.error('错误详情:', { status, data })
      if (status === 401) {
        const userStore = useUserStore()
        userStore.logout()
        window.location.href = "/login"
      }
      ElMessage.error(data.detail || "请求失败")
    } else {
      ElMessage.error("网络错误")
    }
    return Promise.reject(error)
  }
)

export default request