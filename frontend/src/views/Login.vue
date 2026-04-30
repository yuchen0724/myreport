<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2>自定义报表查询系统</h2>
      </template>
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef">
        <el-form-item prop="username">
          <el-input v-model="loginForm.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="loginForm.password" type="password" placeholder="密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="loading" style="width: 100%">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import { ElMessage } from 'element-plus'
import { login, getCurrentUser } from '@/api/auth'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const userStore = useUserStore()
    const loginFormRef = ref(null)
    const loading = ref(false)
    const loginForm = ref({
      username: '',
      password: ''
    })
    const rules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
    }

    // 检查并清理过期 token
    onMounted(() => {
      if (userStore.token) {
        // 清除可能过期的 token，让用户重新登录
        userStore.logout()
      }
    })

    const handleLogin = async () => {
      await loginFormRef.value.validate()
      loading.value = true
      try {
        console.log('开始登录...', loginForm.value)
        const response = await login(loginForm.value.username, loginForm.value.password)
        console.log('登录响应:', response)
        
        // 先设置 token
        userStore.setToken(response.access_token)
        console.log('Token 已设置:', userStore.token)
        
        // 获取完整用户信息（包含 role_id）
        const userResponse = await getCurrentUser()
        console.log('用户信息:', userResponse)
        
        // 设置用户信息（setUser 会自动转换 role_id -> role）
        userStore.setUser(userResponse)
        console.log('用户已设置:', userStore.user, 'role:', userStore.role)
        
        ElMessage.success('登录成功')
        console.log('准备跳转到首页...')
        
        // 使用 nextTick 确保 DOM 更新后再跳转
        await new Promise(resolve => setTimeout(resolve, 100))
        
        await router.push('/')
        console.log('跳转完成')
      } catch (error) {
        console.error('登录失败:', error)
        ElMessage.error('登录失败: ' + (error.message || '未知错误'))
      } finally {
        loading.value = false
      }
    }

    return {
      loginForm,
      rules,
      loginFormRef,
      loading,
      handleLogin
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
}

.login-card h2 {
  text-align: center;
  margin: 0;
}
</style>