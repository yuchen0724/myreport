<template>
  <div class="proxy-server-list">
    <div class="toolbar">
      <el-button type="primary" @click="handleCreate">新建代理服务器</el-button>
      <el-button @click="loadProxyServers">刷新</el-button>
    </div>
    <el-table :data="proxyServers" v-loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="proxy_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag>{{ row.proxy_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="host" label="主机" />
      <el-table-column prop="port" label="端口" width="100" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" @click="handleTest(row)">测试</el-button>
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 测试连接对话框 -->
    <el-dialog v-model="testDialogVisible" title="测试连接" width="400px">
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProxyServerList, deleteProxyServer, testProxyServer } from '@/api/proxy_server'

export default {
  name: 'ProxyServerList',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const proxyServers = ref([])
    const testDialogVisible = ref(false)
    const testResult = ref({ success: false, message: '' })

    const loadProxyServers = async () => {
      loading.value = true
      try {
        proxyServers.value = await getProxyServerList()
      } catch (error) {
        ElMessage.error('加载代理服务器失败')
      } finally {
        loading.value = false
      }
    }

    const handleCreate = () => {
      router.push('/proxy-servers/create')
    }

    const handleEdit = (row) => {
      router.push(`/proxy-servers/${row.id}/edit`)
    }

    const handleDelete = async (row) => {
      try {
        await ElMessageBox.confirm('确定要删除该代理服务器吗？', '提示', { type: 'warning' })
        await deleteProxyServer(row.id)
        ElMessage.success('删除成功')
        loadProxyServers()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
    }

    const handleTest = async (row) => {
      try {
        const res = await testProxyServer({
          proxy_type: row.proxy_type,
          host: row.host,
          port: row.port,
          username: row.username,
          password: row.password_decrypted
        })
        testResult.value = res
      } catch (error) {
        testResult.value = { success: false, message: error.message || '测试失败' }
      }
      testDialogVisible.value = true
    }

    onMounted(() => {
      loadProxyServers()
    })

    return {
      loading,
      proxyServers,
      testDialogVisible,
      testResult,
      loadProxyServers,
      handleCreate,
      handleEdit,
      handleDelete,
      handleTest
    }
  }
}
</script>

<style scoped>
.proxy-server-list {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
}
</style>