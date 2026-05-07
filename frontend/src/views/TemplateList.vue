<!-- frontend/src/views/TemplateList.vue -->
<template>
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
        <el-table-column label="操作" width="350">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" @click="handleShare(row)">分享</el-button>
            <el-button size="small" @click="handleVersions(row)">版本</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 分享对话框 -->
    <el-dialog v-model="shareDialogVisible" title="分享模板" width="500px">
      <el-form :model="shareForm" label-width="100px">
        <el-form-item label="分享给用户">
          <el-select
            v-model="shareForm.user_ids"
            multiple
            placeholder="请选择用户"
            style="width: 100%"
          >
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shareDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmShare">确定</el-button>
      </template>
    </el-dialog>
  </div></template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateList, deleteTemplate } from '@/api/template'
import { shareTemplate } from '@/api/template_share'
import { getUserList } from '@/api/user'

const router = useRouter()
const templates = ref([])
const shareDialogVisible = ref(false)
const shareForm = ref({
  template_id: null,
  user_ids: []
})
const users = ref([])
const usersLoading = ref(false)

onMounted(async () => {
  await loadTemplates()
})

const loadTemplates = async () => {
  try {
    const response = await getTemplateList()
    templates.value = response
  } catch (error) {
    ElMessage.error('加载模板列表失败：' + (error.message || '未知错误'))
  }
}

const loadUsers = async () => {
  if (usersLoading.value || users.value.length > 0) return
  usersLoading.value = true
  try {
    const response = await getUserList()
    users.value = response
  } catch (error) {
    ElMessage.error('加载用户列表失败：' + (error.message || '未知错误'))
  } finally {
    usersLoading.value = false
  }
}

const handleCreate = () => {
  router.push('/templates/create')
}

const handleView = (row) => {
  if (!row?.id) {
    ElMessage.error('模板数据异常，无法查看')
    return
  }
  router.push(`/templates/${row.id}`).catch(err => {
    ElMessage.error('无法查看模板：' + (err.message || '未知错误'))
  })
}

const handleEdit = (row) => {
  if (!row?.id) {
    ElMessage.error('模板数据异常，无法编辑')
    return
  }
  router.push(`/templates/${row.id}/edit`).catch(err => {
    ElMessage.error('无法编辑模板：' + (err.message || '未知错误'))
  })
}

const handleVersions = (row) => {
  if (!row?.id) {
    ElMessage.error('模板数据异常，无法查看版本')
    return
  }
  router.push(`/templates/${row.id}/versions`).catch(err => {
    ElMessage.error('无法查看版本：' + (err.message || '未知错误'))
  })
}

const handleDelete = async (row) => {
  if (!row?.id) {
    ElMessage.error('模板数据异常，无法删除')
    return
  }

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
      ElMessage.error('删除失败：' + (error.message || '未知错误'))
    }
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

const handleShare = (row) => {
  if (!row?.id) {
    ElMessage.error('模板数据异常，无法分享')
    return
  }

  shareForm.value.template_id = row.id
  shareForm.value.user_ids = []
  shareDialogVisible.value = true
  loadUsers()
}

const handleConfirmShare = async () => {
  if (!shareForm.value.template_id) {
    ElMessage.error('模板ID异常，无法分享')
    return
  }

  try {
    await shareTemplate(shareForm.value.template_id, {
      user_ids: shareForm.value.user_ids
    })
    ElMessage.success('分享成功')
    shareDialogVisible.value = false
  } catch (error) {
    ElMessage.error('分享失败：' + (error.message || '未知错误'))
  }
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
