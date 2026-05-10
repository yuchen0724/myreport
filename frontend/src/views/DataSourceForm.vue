<template>
  <div class="datasource-form">
      <el-card>
        <template #header>
          <h2>{{ isEdit ? '编辑数据源' : '新建数据源' }}</h2>
        </template>
        <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
          <el-form-item label="名称" prop="name">
            <el-input v-model="form.name" placeholder="请输入数据源名称" />
          </el-form-item>
          <el-form-item label="类型" prop="type">
            <el-select v-model="form.type" placeholder="请选择数据源类型">
              <el-option label="MySQL" value="MYSQL" />
              <el-option label="PostgreSQL" value="POSTGRESQL" />
              <el-option label="Doris" value="DORIS" />
            </el-select>
          </el-form-item>
          <el-form-item label="主机" prop="host">
            <el-input v-model="form.host" placeholder="请输入主机地址" />
          </el-form-item>
          <el-form-item label="端口" prop="port">
            <el-input-number v-model="form.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="数据库" prop="database">
            <el-input v-model="form.database" placeholder="请输入数据库名称" />
          </el-form-item>
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
          </el-form-item>
          
          <el-divider>代理设置</el-divider>
          
          <el-form-item label="使用代理">
            <el-switch v-model="form.use_proxy" @change="handleProxyChange" />
          </el-form-item>
          
          <el-form-item v-if="form.use_proxy" label="代理服务器" prop="proxy_server_id">
            <el-select v-model="form.proxy_server_id" placeholder="请选择代理服务器" clearable>
              <el-option
                v-for="proxy in proxyServers"
                :key="proxy.id"
                :label="`${proxy.name} (${proxy.host}:${proxy.port})`"
                :value="proxy.id"
              />
            </el-select>
            <el-button size="small" @click="loadProxyServers" style="margin-left: 10px">刷新</el-button>
            <el-button size="small" type="primary" @click="$router.push('/proxy-servers/create')">新建</el-button>
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="handleTest" :loading="testing">测试连接</el-button>
            <el-button @click="handleCancel">取消</el-button>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div></template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createDataSource, updateDataSource, testDataSourceConnection, getDataSource } from '@/api/data_source'
import { getActiveProxyServers } from '@/api/proxy_server'

export default {
  name: 'DataSourceForm',
  components: { },
  setup() {
    const router = useRouter()
    const route = useRoute()
    const formRef = ref(null)
    const testing = ref(false)
    const submitting = ref(false)
    const proxyServers = ref([])
    
    const form = ref({
      name: '',
      type: 'MYSQL',
      host: '',
      port: 3306,
      database: '',
      username: '',
      password: '',
      use_proxy: false,
      proxy_server_id: null
    })
    const rules = {
      name: [{ required: true, message: '请输入数据源名称', trigger: 'blur' }],
      type: [{ required: true, message: '请选择数据源类型', trigger: 'change' }],
      host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
      port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
      database: [{ required: true, message: '请输入数据库名称', trigger: 'blur' }],
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
    }

    const isEdit = computed(() => !!route.params.id)

    const loadProxyServers = async () => {
      try {
        proxyServers.value = await getActiveProxyServers()
      } catch (error) {
        console.error('加载代理服务器失败', error)
      }
    }

    const handleProxyChange = (val) => {
      if (val && proxyServers.value.length === 0) {
        loadProxyServers()
      }
    }

    const handleTest = async () => {
      await formRef.value.validate()
      testing.value = true
      try {
        const result = await testDataSourceConnection(form.value)
        if (result.success) {
          ElMessage.success('连接成功')
        } else {
          ElMessage.error(result.message)
        }
      } catch (error) {
        ElMessage.error('连接测试失败')
      } finally {
        testing.value = false
      }
    }

    const handleSubmit = async () => {
      await formRef.value.validate()
      submitting.value = true
      try {
        if (isEdit.value) {
          await updateDataSource(route.params.id, form.value)
          ElMessage.success('更新成功')
        } else {
          await createDataSource(form.value)
          ElMessage.success('创建成功')
        }
        router.push('/datasources')
      } catch (error) {
        ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
      } finally {
        submitting.value = false
      }
    }

    const handleCancel = () => {
      router.push('/datasources')
    }

    onMounted(async () => {
      // 加载代理服务器列表
      loadProxyServers()
      
      if (isEdit.value) {
        try {
          const data = await getDataSource(route.params.id)
          form.value = {
            name: data.name,
            type: data.type,
            host: data.host,
            port: data.port,
            database: data.database,
            username: data.username,
            password: data.password_decrypted || '',
            use_proxy: data.use_proxy || false,
            proxy_server_id: data.proxy_server_id || null
          }
        } catch (error) {
          ElMessage.error('加载数据源失败')
        }
      }
    })

    return {
      formRef,
      form,
      rules,
      testing,
      submitting,
      isEdit,
      proxyServers,
      loadProxyServers,
      handleProxyChange,
      handleTest,
      handleSubmit,
      handleCancel
    }
  }
}
</script>

<style scoped>
.datasource-form {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}
</style>