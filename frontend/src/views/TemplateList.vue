<!-- frontend/src/views/TemplateList.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="template-list">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>模板管理</span>
            <el-button type="primary" @click="handleCreate">新建模板</el-button>
          </div>
        </template>

      <el-table :data="templates" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_public ? 'success' : 'info'">
              {{ row.is_public ? '公开' : '私有' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" @click="handleVersions(row)">版本</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateList, deleteTemplate } from '@/api/template'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

const router = useRouter()
const templates = ref([])

onMounted(async () => {
  await loadTemplates()
})

const loadTemplates = async () => {
  try {
    const response = await getTemplateList()
    templates.value = response
  } catch (error) {
    ElMessage.error('加载模板列表失败')
  }
}

const handleCreate = () => {
  router.push('/templates/create')
}

const handleView = (row) => {
  router.push(`/templates/${row.id}`)
}

const handleEdit = (row) => {
  router.push(`/templates/${row.id}/edit`)
}

const handleVersions = (row) => {
  router.push(`/templates/${row.id}/versions`)
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该模板吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await deleteTemplate(row.id)
    ElMessage.success('删除成功')
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<style scoped>
.template-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
