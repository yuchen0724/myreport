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
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

export default {
  name: 'App',
  components: { Header, Sidebar },
  setup() {
    const route = useRoute()
    const userStore = useUserStore()

    const isLoginPage = computed(() => route.path === '/login')

    // 初始化时检查 token
    onMounted(() => {
      // 登录页：始终清除可能过期的 token
      if (isLoginPage.value) {
        const token = localStorage.getItem('token')
        if (token) {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          userStore.token = ''
          userStore.user = null
          console.log('已清除过期 token')
        }
      } else {
        // 非登录页：恢复 token
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
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
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
  background: #409eff;
  color: white;
}

.main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 200px;
  background: #304156;
  color: white;
}

.content {
  flex: 1;
  overflow-y: auto;
  background: #f0f2f5;
}
</style>
