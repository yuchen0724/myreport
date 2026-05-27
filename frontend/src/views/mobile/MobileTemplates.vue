<template>
  <div class="mobile-templates">
    <!-- 顶部标题和操作 -->
    <div class="mobile-page-header">
      <h2>模板管理</h2>
      <el-button type="primary" size="small" @click="handleCreate">
        + 新建
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索模板..."
        clearable
        :prefix-icon="Search"
      />
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="mobile-loading">
      <el-skeleton :rows="3" animated v-for="i in 3" :key="i" style="margin-bottom: 12px" />
    </div>

    <!-- 错误提示 -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon closable @close="error = ''" />

    <!-- 空状态 -->
    <el-empty v-else-if="filteredTemplates.length === 0" description="暂无模板" />

    <!-- 模板卡片列表 -->
    <div v-else class="template-cards">
      <div
        v-for="template in filteredTemplates"
        :key="template.id"
        class="template-card"
        @click="handleView(template)"
      >
        <div class="template-card-header">
          <div class="template-name">{{ template.name }}</div>
          <el-tag :type="template.is_public ? 'success' : 'info'" size="small">
            {{ template.is_public ? '公开' : '私有' }}
          </el-tag>
        </div>
        <div class="template-desc">
          {{ template.description || '暂无描述' }}
        </div>
        <div class="template-meta">
          <span>v{{ template.version }}</span>
          <span>{{ formatDate(template.created_at) }}</span>
        </div>
        <div class="template-actions" @click.stop>
          <el-button text size="small" @click="handleEdit(template)">编辑</el-button>
          <el-button text size="small" @click="handleShare(template)">分享</el-button>
          <el-button text size="small" type="danger" @click="handleDelete(template)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- 分享对话框 -->
    <el-dialog v-model="shareDialogVisible" title="分享模板" width="90%" :close-on-click-modal="false">
      <el-form :model="shareForm" label-position="top">
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getTemplateList, deleteTemplate } from '@/api/template'
import { shareTemplate } from '@/api/template_share'
import { getUserList } from '@/api/user'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const templates = ref([])
const searchQuery = ref('')

const shareDialogVisible = ref(false)
const shareForm = ref({ template_id: null, user_ids: [] })
const users = ref([])

const filteredTemplates = computed(() => {
  if (!searchQuery.value) return templates.value
  const q = searchQuery.value.toLowerCase()
  return templates.value.filter(t =>
    t.name?.toLowerCase().includes(q) ||
    t.description?.toLowerCase().includes(q)
  )
})

const loadTemplates = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await getTemplateList()
    templates.value = response
  } catch (err) {
    error.value = '加载模板列表失败'
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const response = await getUserList()
    users.value = response
  } catch {
    ElMessage.error('加载用户列表失败')
  }
}

const handleCreate = () => router.push('/templates/create')
const handleView = (row) => router.push(`/templates/${row.id}`)
const handleEdit = (row) => router.push(`/templates/${row.id}/edit`)

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
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleShare = (row) => {
  shareForm.value.template_id = row.id
  shareForm.value.user_ids = []
  shareDialogVisible.value = true
  loadUsers()
}

const handleConfirmShare = async () => {
  try {
    await shareTemplate(shareForm.value.template_id, {
      user_ids: shareForm.value.user_ids
    })
    ElMessage.success('分享成功')
    shareDialogVisible.value = false
  } catch (err) {
    ElMessage.error('分享失败')
  }
}

const formatDate = (date) => {
  if (!date) return ''
  try {
    const d = new Date(date)
    const pad = n => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  } catch {
    return date
  }
}

onMounted(() => loadTemplates())
</script>

<style scoped>
.mobile-templates {
  padding: 16px;
  padding-bottom: 80px;
}

.mobile-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.mobile-page-header h2 {
  font-size: 22px;
  font-weight: 600;
  margin: 0;
}

.search-bar {
  margin-bottom: 16px;
}

.mobile-loading {
  padding: 12px 0;
}

.template-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-card {
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.15s;
}

.template-card:active {
  transform: scale(0.99);
}

.template-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.template-name {
  font-size: 16px;
  font-weight: 600;
}

.template-desc {
  font-size: 13px;
  color: var(--text-secondary, #909399);
  margin-bottom: 8px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.template-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary, #909399);
  margin-bottom: 10px;
}

.template-actions {
  display: flex;
  gap: 4px;
  border-top: 1px solid var(--border-color, #ebeef5);
  padding-top: 8px;
}
</style>
