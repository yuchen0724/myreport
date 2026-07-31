import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { resolve } from "path"
import AutoImport from "unplugin-auto-import/vite"
import Components from "unplugin-vue-components/vite"
import { ElementPlusResolver } from "unplugin-vue-components/resolvers"

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "src")
    }
  },
  build: {
    // 代码分割优化
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/element-plus/')) {
            return 'element-plus'
          }
          if (
            id.includes('/node_modules/vue/') ||
            id.includes('/node_modules/vue-router/') ||
            id.includes('/node_modules/pinia/')
          ) {
            return 'vue-vendor'
          }
        }
      }
    },
    // 启用CSS代码分割
    cssCodeSplit: true,
    // 启用压缩，并让 terserOptions 生效
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
