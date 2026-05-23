<template>
  <div id="app">
    <!-- 登录页不需要布局 -->
    <router-view v-if="isLoginPage" />
    
    <!-- 其他页面使用全局布局 -->
    <div v-else class="layout">
      <div class="header">
        <Header />
      </div>
      <div class="main">
        <div class="sidebar">
          <Sidebar />
        </div>
        <div class="content">
          <router-view />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

export default {
  name: 'App',
  components: { Header, Sidebar },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const userStore = useUserStore()

    const isLoginPage = computed(() => route.path === '/login')

    // 监听路由变化，始终确保登录页不发送认证请求
    watch(isLoginPage, (newVal) => {
      if (newVal) {
        // 进入登录页，清除 token
        userStore.logout()
      }
    }, { immediate: true })

    // 初始化时检查 token（非登录页才恢复）
    onMounted(() => {
      if (!isLoginPage.value) {
        const token = localStorage.getItem('token')
        const user = localStorage.getItem('user')
        if (token && user) {
          userStore.setToken(token)
          userStore.setUser(JSON.parse(user))
        }
      }
    })

    return { isLoginPage }
  }
}
</script>

<style>
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f0f2f5;
  --bg-header: #409eff;
  --bg-sidebar: #304156;
  --text-primary: #303133;
  --text-secondary: #606266;
  --text-light: #ffffff;
  --border-color: #dcdfe6;
}

html.dark {
  --bg-primary: #1a1a1a;
  --bg-secondary: #141414;
  --bg-header: #1d7cff;
  --bg-sidebar: #1f1f1f;
  --text-primary: #e5e5e5;
  --text-secondary: #a3a3a3;
  --text-light: #ffffff;
  --border-color: #404040;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--bg-secondary);
  color: var(--text-primary);
}

#app {
  height: 100vh;
  overflow: hidden;
}

.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.header {
  height: 60px;
  background: var(--bg-header);
  color: var(--text-light);
}

.main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 200px;
  background: var(--bg-sidebar);
  color: var(--text-light);
}

.content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-secondary);
}
</style>
