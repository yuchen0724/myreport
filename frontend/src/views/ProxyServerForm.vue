<template>
  <div class="proxy-server-form">
    <el-page-header @back="goBack" :content="isEdit ? '编辑代理服务器' : '新建代理服务器'" />
    
    <el-card class="form-card">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="代理服务器名称" />
        </el-form-item>
        
        <el-form-item label="代理类型" prop="proxy_type">
          <el-select v-model="form.proxy_type" placeholder="选择代理类型">
            <el-option label="HTTP" value="http" />
            <el-option label="HTTPS" value="https" />
            <el-option label="SOCKS5" value="socks5" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="主机" prop="host">
          <el-input v-model="form.host" placeholder="代理服务器地址" />
        </el-form-item>
        
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="可选" />
        </el-form-item>
        
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="可选，留空则不修改" show-password />
        </el-form-item>
        
        <el-form-item label="启用状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
          <el-button @click="handleTest" :loading="testing">测试连接</el-button>
          <el-button @click="goBack">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 测试结果对话框 -->
    <el-dialog v-model="testDialogVisible" title="测试连��" width="400px">
      <el-result
        :icon="testResult.success ? 'success' : 'error'"
        :title="testResult.success ? '连接成功' : '连接失败'"
        :sub-title="testResult.message"
      >
        <template #extra>
          <el-button @click="testDialogVisible = false">关闭</el-button>
        </template>
      </el-result>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProxyServer, createProxyServer, updateProxyServer, testProxyServer } from '@/api/proxy_server'

export default {
  name: 'ProxyServerForm',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const formRef = ref(null)
    const submitting = ref(false)
    const testing = ref(false)
    const testDialogVisible = ref(false)
    const testResult = ref({ success: false, message: '' })

    const isEdit = computed(() => !!route.params.id)
    
    const form = ref({
      name: '',
      proxy_type: 'http',
      host: '',
      port: 8080,
      username: '',
      password: '',
      is_active: true
    })

    const rules = {
      name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
      proxy_type: [{ required: true, message: '请选择代理类型', trigger: 'change' }],
      host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
      port: [{ required: true, message: '请输入端口', trigger: 'blur' }]
    }

    const loadData = async () => {
      if (isEdit.value) {
        try {
          const data = await getProxyServer(route.params.id)
          form.value = {
            name: data.name,
            proxy_type: data.proxy_type,
            host: data.host,
            port: data.port,
            username: data.username || '',
            password: '',  // 不回填密码
            is_active: data.is_active
          }
        } catch (error) {
          ElMessage.error('加载代理服务器失败')
        }
      }
    }

    const handleSubmit = async () => {
      const valid = await formRef.value.validate().catch(() => false)
      if (!valid) return

      submitting.value = true
      try {
        const data = { ...form.value }
        // 空密码不提交
        if (!data.password) {
          delete data.password
        }
        
        if (isEdit.value) {
          await updateProxyServer(route.params.id, data)
          ElMessage.success('更新成功')
        } else {
          await createProxyServer(data)
          ElMessage.success('创建成功')
        }
        router.push('/proxy-servers')
      } catch (error) {
        ElMessage.error(error.message || '操作失败')
      } finally {
        submitting.value = false
      }
    }

    const handleTest = async () => {
      testing.value = true
      try {
        const res = await testProxyServer({
          proxy_type: form.value.proxy_type,
          host: form.value.host,
          port: form.value.port,
          username: form.value.username || null,
          password: form.value.password || null
        })
        testResult.value = res
      } catch (error) {
        testResult.value = { success: false, message: error.message || '测试失败' }
      } finally {
        testing.value = false
      }
      testDialogVisible.value = true
    }

    const goBack = () => {
      router.push('/proxy-servers')
    }

    onMounted(() => {
      loadData()
    })

    return {
      formRef,
      form,
      rules,
      isEdit,
      submitting,
      testing,
      testDialogVisible,
      testResult,
      handleSubmit,
      handleTest,
      goBack
    }
  }
}
</script>

<style scoped>
.proxy-server-form {
  padding: 20px;
}

.form-card {
  margin-top: 20px;
  max-width: 600px;
}
</style>