<template>
  <div id="app">
    <!-- 登录页不需要布局 -->
    <router-view v-if="isLoginPage" />

    <!-- 移动端布局 -->
    <div v-else-if="isMobile" class="mobile-layout">
      <!-- 移动端顶部栏 -->
      <div class="mobile-header">
        <div class="mobile-header-left">
          <el-icon :size="22" class="menu-toggle" @click="toggleMobileMenu">
            <component :is="mobileMenuVisible ? 'Close' : 'Expand'" />
          </el-icon>
          <span class="mobile-title">自定义报表</span>
        </div>
        <div class="mobile-header-right">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              {{ user?.username || '用户' }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 移动端侧边栏遮罩 -->
      <div
        v-if="mobileMenuVisible"
        class="mobile-overlay"
        @click="closeMobileMenu"
      />

      <!-- 移动端侧边栏 -->
      <transition name="slide-left">
        <div v-if="mobileMenuVisible" class="mobile-sidebar">
          <MobileSidebar @navigate="closeMobileMenu" />
        </div>
      </transition>

      <!-- 移动端内容区域 -->
      <div class="mobile-content">
        <router-view />
      </div>
    </div>

    <!-- 桌面端布局 -->
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
import MobileSidebar from '@/components/MobileSidebar.vue'
import { useMobile } from '@/composables/useMobile'
import { ArrowDown, Close, Expand } from '@element-plus/icons-vue'

export default {
  name: 'App',
  components: { Header, Sidebar, MobileSidebar, ArrowDown, Close, Expand },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const userStore = useUserStore()
    const {
      isMobile,
      mobileMenuVisible,
      toggleMobileMenu,
      closeMobileMenu,
    } = useMobile()

    const isLoginPage = computed(() => route.path === '/login')
    const user = computed(() => userStore.user)

    // 监听路由变化，移动端自动关闭菜单
    watch(() => route.path, () => {
      if (isMobile.value) {
        closeMobileMenu()
      }
    })

    // 监听路由变化，始终确保登录页不发送认证请求
    watch(isLoginPage, (newVal) => {
      if (newVal) {
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

    const handleCommand = (command) => {
      if (command === 'logout') {
        userStore.logout()
        router.push('/login')
      }
    }

    return {
      isLoginPage,
      isMobile,
      user,
      mobileMenuVisible,
      toggleMobileMenu,
      closeMobileMenu,
      handleCommand,
    }
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

/* ===== 桌面端布局 ===== */
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

/* ===== 移动端布局 ===== */
.mobile-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.mobile-header {
  height: 50px;
  background: var(--bg-header);
  color: var(--text-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  flex-shrink: 0;
  z-index: 200;
}

.mobile-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.menu-toggle {
  cursor: pointer;
  padding: 4px;
}

.mobile-title {
  font-size: 16px;
  font-weight: 600;
}

.mobile-header-right .el-dropdown-link {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-light);
  cursor: pointer;
}

.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 300;
}

.mobile-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 260px;
  background: var(--bg-sidebar);
  color: var(--text-light);
  z-index: 310;
  overflow-y: auto;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-secondary);
  -webkit-overflow-scrolling: touch;
}

/* ===== 移动端动画 ===== */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.25s ease;
}

.slide-left-enter-from,
.slide-left-leave-to {
  transform: translateX(-100%);
}

/* ===== 小屏幕适配 ===== */
@media (max-width: 768px) {
  .sidebar {
    display: none;
  }

  .header {
    height: 50px;
  }

  .content {
    padding: 0;
  }
}

@media (max-width: 480px) {
  .el-dialog {
    margin: 10px;
    width: calc(100% - 20px) !important;
  }

  .el-drawer {
    width: 100% !important;
  }
}
</style>
