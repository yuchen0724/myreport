import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { resolve } from "path"

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src")
    }
  },
  build: {
    // 代码分割优化
    rollupOptions: {
      output: {
        manualChunks: {
          // 将Element Plus单独打包
          'element-plus': ['element-plus'],
          // 将ECharts单独打包
          'echarts': ['echarts'],
          // 将Vue相关库单独打包
          'vue-vendor': ['vue', 'vue-router', 'pinia']
        }
      }
    },
    // 启用CSS代码分割
    cssCodeSplit: true,
    // 启用压缩
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // 生产环境移除console
        drop_debugger: true // 移除debugger
      }
    },
    // 设置chunk大小警告限制
    chunkSizeWarningLimit: 1000
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
})