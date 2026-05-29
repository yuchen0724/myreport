<template>
  <div class="header">
    <div class="logo">自定义报表查询系统</div>
    <div class="user-info">
      <!-- 主题切换 -->
      <el-switch
        v-model="themeStore.isDark"
        inline-prompt
        :active-icon="Sunny"
        :inactive-icon="Moon"
        size="small"
        @change="handleThemeToggle"
        class="theme-toggle"
      />
      <el-dropdown @command="handleCommand">
        <span class="el-dropdown-link">
          {{ user?.username || '用户' }}
          <el-icon><arrow-down /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import { useThemeStore } from '@/store/theme'
import { ArrowDown, Moon, Sunny } from '@element-plus/icons-vue'

export default {
  name: 'Header',
  components: { ArrowDown },
  setup() {
    const router = useRouter()
    const userStore = useUserStore()
    const themeStore = useThemeStore()
    const user = computed(() => userStore.user)

    const handleCommand = (command) => {
      if (command === 'logout') {
        userStore.logout()
        router.push('/login')
      }
    }

    const handleThemeToggle = () => {
      themeStore.toggleTheme()
    }

    return { user, handleCommand, themeStore, handleThemeToggle, Moon, Sunny }
  }
}
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 100%;
}

.logo {
  font-size: 18px;
  font-weight: bold;
}

.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 16px;
}

.theme-toggle {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  display: flex;
  align-items: center;
  gap: 5px;
}
</style>
