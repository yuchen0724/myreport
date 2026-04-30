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
import { shareTemplate, getSharedTemplates } from '@/api/template_share'
const router = useRouter()
const templates = ref([])
const shareDialogVisible = ref(false)
const shareForm = ref({
  template_id: null,
  user_ids: []
})
const users = ref([
  { id: 1, username: 'admin' },
  { id: 2, username: 'user1' },
  { id: 3, username: 'user2' }
])

onMounted(async () => {
  await loadTemplates()
})

const loadTemplates = async () => {
  try {
    console.log('开始加载模板列表...')
    const response = await getTemplateList()
    console.log('模板列表响应:', response)
    templates.value = response
    console.log('模板列表已更新，共', templates.value.length, '个模板')
  } catch (error) {
    console.error('加载模板列表失败:', error)
    console.error('错误详情:', {
      message: error.message,
      response: error.response,
      request: error.request
    })
    ElMessage.error('加载模板列表失败：' + (error.message || '未知错误'))
  }
}

const handleCreate = () => {
  router.push('/templates/create')
}

const handleView = (row) => {
  console.log('查看模板 - row对象:', row)
  console.log('查看模板 - row.id:', row.id)
  
  if (!row || !row.id) {
    console.error('row对象或row.id为空')
    ElMessage.error('模板数据异常，无法查看')
    return
  }
  
  console.log('准备跳转到模板详情页面，ID:', row.id)
  router.push(`/templates/${row.id}`).catch(err => {
    console.error('路由跳转失败:', err)
    ElMessage.error('无法查看模板：' + (err.message || '未知错误'))
  })
}

const handleEdit = (row) => {
  console.log('编辑模板 - row对象:', row)
  console.log('编辑模板 - row.id:', row.id)
  
  if (!row || !row.id) {
    console.error('row对象或row.id为空')
    ElMessage.error('模板数据异常，无法编辑')
    return
  }
  
  console.log('准备跳转到模板编辑页面，ID:', row.id)
  router.push(`/templates/${row.id}/edit`).catch(err => {
    console.error('路由跳转失败:', err)
    ElMessage.error('无法编辑模板：' + (err.message || '未知错误'))
  })
}

const handleVersions = (row) => {
  console.log('查看版本历史 - row对象:', row)
  console.log('查看版本历史 - row.id:', row.id)
  
  if (!row || !row.id) {
    console.error('row对象或row.id为空')
    ElMessage.error('模板数据异常，无法查看版本')
    return
  }
  
  console.log('准备跳转到版本历史页面，ID:', row.id)
  router.push(`/templates/${row.id}/versions`).catch(err => {
    console.error('路由跳转失败:', err)
    ElMessage.error('无法查看版本：' + (err.message || '未知错误'))
  })
}

const handleDelete = async (row) => {
  console.log('删除模板 - row对象:', row)
  console.log('删除模板 - row.id:', row.id)
  
  if (!row || !row.id) {
    console.error('row对象或row.id为空')
    ElMessage.error('模板数据异常，无法删除')
    return
  }
  
  try {
    await ElMessageBox.confirm('确定要删除该模板吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    console.log('开始删除模板，ID:', row.id)
    await deleteTemplate(row.id)
    ElMessage.success('删除成功')
    await loadTemplates()
  } catch (error) {
    console.error('删除模板失败:', error)
    if (error !== 'cancel') {
      ElMessage.error('删除失败：' + (error.message || '未知错误'))
    }
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

const handleShare = (row) => {
  console.log('分享模板 - row对象:', row)
  console.log('分享模板 - row.id:', row.id)
  
  if (!row || !row.id) {
    console.error('row对象或row.id为空')
    ElMessage.error('模板数据异常，无法分享')
    return
  }
  
  console.log('准备打开分享对话框，模板ID:', row.id)
  shareForm.value.template_id = row.id
  shareForm.value.user_ids = []
  shareDialogVisible.value = true
}

const handleConfirmShare = async () => {
  console.log('确认分享模板 - shareForm:', shareForm.value)
  
  if (!shareForm.value.template_id) {
    console.error('template_id为空')
    ElMessage.error('模板ID异常，无法分享')
    return
  }
  
  try {
    console.log('开始分享模板，ID:', shareForm.value.template_id, '用户IDs:', shareForm.value.user_ids)
    await shareTemplate(shareForm.value.template_id, {
      user_ids: shareForm.value.user_ids
    })
    ElMessage.success('分享成功')
    shareDialogVisible.value = false
  } catch (error) {
    console.error('分享模板失败:', error)
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
