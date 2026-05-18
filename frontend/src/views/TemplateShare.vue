<!-- frontend/src/views/TemplateShare.vue -->
<template>
  <div class="template-share">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>模板分享管理</span>
          </div>
        </template>

        <el-tabs v-model="activeTab" @tab-change="handleTabChange">
          <!-- 分享我的模板 -->
          <el-tab-pane label="分享我的模板" name="share">
            <el-form :model="shareForm" :rules="shareRules" ref="shareFormRef" label-width="120px">
              <el-form-item label="选择模板" prop="template_id">
                <el-select
                  v-model="shareForm.template_id"
                  placeholder="请选择模板"
                  style="width: 100%"
                  @change="handleTemplateChange"
                >
                  <el-option
                    v-for="template in myTemplates"
                    :key="template.id"
                    :label="template.name"
                    :value="template.id"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="分享给用户" prop="user_ids">
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

              <el-form-item>
                <el-button type="primary" @click="handleShare" :loading="shareLoading">
                  分享模板
                </el-button>
                <el-button @click="resetShareForm">重置</el-button>
              </el-form-item>
            </el-form>

            <el-divider />

            <div class="share-history">
              <h4>我的分享记录</h4>
              <StaticTableEnhancer :columns="shareHistoryColumns" :data="shareHistory" table-id="template-share-history">
                <template #shared_users="{ row }">
                  <el-tag
                    v-for="user in row.shared_users"
                    :key="user.id"
                    style="margin-right: 5px"
                  >
                    {{ user.username }}
                  </el-tag>
                </template>
                <template #shared_at="{ row }">
                  {{ formatDate(row.shared_at) }}
                </template>
              </StaticTableEnhancer>
            </div>
          </el-tab-pane>

          <!-- 分享给我的模板 -->
          <el-tab-pane label="分享给我的模板" name="shared">
            <StaticTableEnhancer :columns="sharedToMeColumns" :data="sharedToMe" :loading="sharedLoading" table-id="template-shared-to-me">
              <template #shared_by="{ row }">
                {{ row.shared_by_username || row.shared_by }}
              </template>
              <template #shared_at="{ row }">
                {{ formatDate(row.shared_at) }}
              </template>
              <template #operations="{ row }">
                <el-button size="small" @click="handleUseTemplate(row)">使用</el-button>
                <el-button size="small" type="primary" @click="handleViewTemplate(row)">查看</el-button>
              </template>
            </StaticTableEnhancer>
          </el-tab-pane>

          <!-- 分享详情 -->
          <el-tab-pane label="分享详情" name="detail">
            <el-form :model="detailForm" label-width="120px">
              <el-form-item label="选择模板">
                <el-select
                  v-model="detailForm.template_id"
                  placeholder="请选择模板"
                  style="width: 100%"
                  @change="handleDetailTemplateChange"
                >
                  <el-option
                    v-for="template in myTemplates"
                    :key="template.id"
                    :label="template.name"
                    :value="template.id"
                  />
                </el-select>
              </el-form-item>
            </el-form>

            <el-divider />

            <div v-if="templateShares.length > 0">
              <h4>模板分享详情</h4>
              <StaticTableEnhancer :columns="templateSharesColumns" :data="templateShares" :loading="detailLoading" table-id="template-share-detail">
                <template #shared_at="{ row }">
                  {{ formatDate(row.shared_at) }}
                </template>
                <template #operations="{ row }">
                  <el-button size="small" type="danger" @click="handleRevokeShare(row)">
                    取消分享
                  </el-button>
                </template>
              </StaticTableEnhancer>
            </div>
            <el-empty v-else description="请选择模板查看分享详情" />
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div></template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateList } from '@/api/template'
import { shareTemplate, getSharedTemplates, getTemplateShares, unshareTemplate } from '@/api/template_share'
import { getUserList } from '@/api/user'
import StaticTableEnhancer from '@/components/StaticTableEnhancer.vue'

const router = useRouter()
const activeTab = ref('share')
const shareFormRef = ref(null)

// 分享表单
const shareForm = ref({
  template_id: null,
  user_ids: []
})

const shareRules = {
  template_id: [{ required: true, message: '请选择模板', trigger: 'change' }],
  user_ids: [{ required: true, message: '请选择分享用户', trigger: 'change' }]
}

// 详情表单
const detailForm = ref({
  template_id: null
})

// 数据
const myTemplates = ref([])
const users = ref([])
const sharedToMe = ref([])
const templateShares = ref([])
const shareHistory = ref([])

// 加载状态
const shareLoading = ref(false)
const sharedLoading = ref(false)
const detailLoading = ref(false)

// 表格列定义
const shareHistoryColumns = [
  { prop: 'template_name', label: '模板名称' },
  { prop: 'shared_users', label: '分享给用户', slotName: 'shared_users' },
  { prop: 'shared_at', label: '分享时间', width: 180, slotName: 'shared_at' },
]

const sharedToMeColumns = [
  { prop: 'id', label: 'ID', width: 80 },
  { prop: 'name', label: '模板名称' },
  { prop: 'description', label: '描述' },
  { prop: 'shared_by', label: '分享者', width: 120, slotName: 'shared_by' },
  { prop: 'shared_at', label: '分享时间', width: 180, slotName: 'shared_at' },
  { prop: 'operations', label: '操作', width: 150, slotName: 'operations' },
]

const templateSharesColumns = [
  { prop: 'username', label: '用户名' },
  { prop: 'email', label: '邮箱' },
  { prop: 'shared_at', label: '分享时间', width: 180, slotName: 'shared_at' },
  { prop: 'operations', label: '操作', width: 100, slotName: 'operations' },
]

// 日期格式化
const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 加载我的模板列表
const loadMyTemplates = async () => {
  try {
    const response = await getTemplateList()
    myTemplates.value = response || []
  } catch (error) {
    console.error('加载模板列表失败:', error)
    ElMessage.error('加载模板列表失败')
  }
}

// 加载用户列表
const loadUsers = async () => {
  try {
    const response = await getUserList()
    users.value = response || []
  } catch (error) {
    console.error('加载用户列表失败:', error)
    ElMessage.error('加载用户列表失败')
  }
}

// 加载分享给我的模板
const loadSharedToMe = async () => {
  sharedLoading.value = true
  try {
    const response = await getSharedTemplates()
    sharedToMe.value = response || []
  } catch (error) {
    console.error('加载分享给我的模板失败:', error)
    ElMessage.error('加载分享给我的模板失败')
  } finally {
    sharedLoading.value = false
  }
}

// 加载模板分享详情
const loadTemplateShares = async (templateId) => {
  if (!templateId) {
    templateShares.value = []
    return
  }

  detailLoading.value = true
  try {
    const response = await getTemplateShares(templateId)
    templateShares.value = response || []
  } catch (error) {
    console.error('加载模板分享详情失败:', error)
    ElMessage.error('加载模板分享详情失败')
  } finally {
    detailLoading.value = false
  }
}

// 标签页切换
const handleTabChange = (tabName) => {
  if (tabName === 'shared') {
    loadSharedToMe()
  }
}

// 模板选择变化
const handleTemplateChange = (templateId) => {
  // 可以在这里加载该模板已有的分享记录
}

// 详情模板选择变化
const handleDetailTemplateChange = (templateId) => {
  loadTemplateShares(templateId)
}

// 分享模板
const handleShare = async () => {
  if (!shareFormRef.value) return

  try {
    await shareFormRef.value.validate()
  } catch (error) {
    return
  }

  shareLoading.value = true
  try {
    await shareTemplate(shareForm.value.template_id, {
      user_ids: shareForm.value.user_ids
    })

    ElMessage.success('分享成功')

    // 添加到分享历史
    const template = myTemplates.value.find(t => t.id === shareForm.value.template_id)
    const sharedUsers = users.value.filter(u => shareForm.value.user_ids.includes(u.id))

    shareHistory.value.unshift({
      template_name: template?.name || '未知模板',
      shared_users: sharedUsers,
      shared_at: new Date().toISOString()
    })

    // 重置表单
    resetShareForm()
  } catch (error) {
    console.error('分享失败:', error)
    ElMessage.error(error.response?.data?.detail || '分享失败')
  } finally {
    shareLoading.value = false
  }
}

// 重置分享表单
const resetShareForm = () => {
  shareForm.value = {
    template_id: null,
    user_ids: []
  }
  if (shareFormRef.value) {
    shareFormRef.value.clearValidate()
  }
}

// 使用模板
const handleUseTemplate = (row) => {
  ElMessage.info('使用模板功能开发中...')
  // TODO: 实现使用模板的逻辑
}

// 查看模板
const handleViewTemplate = (row) => {
  router.push(`/templates/${row.id}`)
}

// 取消分享
const handleRevokeShare = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要取消分享给用户 ${row.username} 吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const response = await unshareTemplate(detailForm.value.template_id, row.user_id)
    if (response.success) {
      ElMessage.success('取消分享成功')
      // 重新加载分享详情
      if (detailForm.value.template_id) {
        loadTemplateShares(detailForm.value.template_id)
      }
    } else {
      ElMessage.error('取消分享失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('取消分享失败:', error)
      ElMessage.error(error.response?.data?.detail || '取消分享失败')
    }
  }
}

// 初始化
onMounted(async () => {
  await loadMyTemplates()
  await loadUsers()
})
</script>

<style scoped>
.template-share {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.share-history {
  margin-top: 20px;
}

.share-history h4 {
  margin-bottom: 10px;
  color: #606266;
}

.el-divider {
  margin: 20px 0;
}
</style>
