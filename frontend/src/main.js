import { createApp } from "vue"
import { createPinia } from "pinia"
import "element-plus/theme-chalk/dark/css-vars.css"
import {
  Edit, Delete, Search, Plus, Refresh,
  Download, Upload, Back, Check, Close,
  ArrowDown, ArrowUp, User, Lock, Setting,
  Document, Folder, DataAnalysis, PieChart,
  TrendCharts, Histogram
} from "@element-plus/icons-vue"
import App from "./App.vue"
import router from "./router"
import "./style.css"

// 全局错误捕获
const app = createApp(App)

// Vue 错误处理
app.config.errorHandler = (err, instance, info) => {
  console.error('Vue Error:', err)
  console.error('Component:', instance)
  console.error('Info:', info)
}

// 未捕获的 Promise 错误
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled Promise Rejection:', event.reason)
})

const pinia = createPinia()

// 按需注册常用图标
const icons = {
  Edit, Delete, Search, Plus, Refresh,
  Download, Upload, Back, Check, Close,
  ArrowDown, ArrowUp, User, Lock, Setting,
  Document, Folder, DataAnalysis, PieChart,
  TrendCharts, Histogram
}
for (const [key, component] of Object.entries(icons)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.mount("#app")
