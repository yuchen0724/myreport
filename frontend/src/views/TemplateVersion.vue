<!-- frontend/src/views/TemplateVersion.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="template-version">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>模板版本管理</span>
            <el-button @click="handleBack">返回</el-button>
          </div>
        </template>

        <el-table :data="versions" style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="version" label="版本号" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_by" label="创建者" width="100" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="handleView(row)">查看</el-button>
              <el-button size="small" type="primary" @click="handleRollback(row)">回滚</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 配置预览对话框 -->
        <el-dialog v-model="configDialogVisible" title="配置预览" width="60%">
          <pre>{{ currentConfig }}</pre>
        </el-dialog>
      </el-card>
    </div>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateVersions, rollbackTemplate } from '@/api/template'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

const router = useRouter()
const route = useRoute()
const versions = ref([])
const configDialogVisible = ref(false)
const currentConfig = ref('')

onMounted(async () => {
  await loadVersions()
})

const loadVersions = async () => {
  try {
    const response = await getTemplateVersions(route.params.id)
    versions.value = response
  } catch (error) {
    ElMessage.error('加载版本列表失败')
  }
}

const handleView = (row) => {
  currentConfig.value = JSON.stringify(row.config, null, 2)
  configDialogVisible.value = true
}

const handleRollback = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 ${row.version} 吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await rollbackTemplate(route.params.id, row.version)
    ElMessage.success('回滚成功')
    await loadVersions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('回滚失败')
    }
  }
}

const handleBack = () => {
  console.log('返回上一页')
  // 尝试返回上一页，如果没有历史记录则返回模板列表
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/templates')
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<style scoped>
.template-version {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

pre {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>
