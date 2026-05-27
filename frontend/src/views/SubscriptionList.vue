<template>
  <div class="subscriptions">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>查询订阅推送</h3>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon> 新建订阅
          </el-button>
        </div>
      </template>

      <el-table :data="subscriptions" v-loading="loading" stripe>
        <el-table-column prop="template_name" label="模板名称" min-width="150">
          <template #default="{ row }">
            {{ row.template_name || `模板#${row.template_id}` }}
          </template>
        </el-table-column>
        <el-table-column prop="cron_expression" label="Cron 表达式" width="160" />
        <el-table-column prop="notify_channel" label="通知渠道" width="100">
          <template #default="{ row }">
            <el-tag :type="row.notify_channel === 'feishu' ? 'success' : 'info'" size="small">
              {{ row.notify_channel === 'feishu' ? '飞书' : '邮件' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="上次执行" width="180">
          <template #default="{ row }">
            {{ row.last_run_at ? new Date(row.last_run_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleToggle(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="handleRunNow(row)">立即执行</el-button>
            <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
            <el-button size="small" @click="showExecutions(row)">历史</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑订阅' : '新建订阅'" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="模板 ID">
          <el-input-number v-model="form.template_id" :min="1" :disabled="!!editId" />
          <span class="form-hint">选择要订阅的模板</span>
        </el-form-item>
        <el-form-item label="Cron 表达式">
          <el-input v-model="form.cron_expression" placeholder="如：0 8 * * 1 (每周一早8点)">
            <template #append>
              <el-button @click="checkNextRun">下次执行</el-button>
            </template>
          </el-input>
          <div v-if="nextRunHint" class="next-run-hint">
            下次执行时间: {{ nextRunHint }}
          </div>
        </el-form-item>
        <el-form-item label="通知渠道">
          <el-radio-group v-model="form.notify_channel">
            <el-radio value="feishu">飞书</el-radio>
            <el-radio value="email">邮件</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 执行历史对话框 -->
    <el-dialog v-model="executionDialogVisible" title="执行历史" width="700px">
      <el-table :data="executions" v-loading="executionLoading" stripe>
        <el-table-column prop="executed_at" label="执行时间" width="200">
          <template #default="{ row }">
            {{ row.executed_at ? new Date(row.executed_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result_summary" label="结果摘要" min-width="200">
          <template #default="{ row }">
            {{ row.result_summary || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.error_message || ''" placement="top" v-if="row.error_message">
              <span class="error-text">{{ row.error_message.substring(0, 50) }}...</span>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  listSubscriptions, createSubscription, updateSubscription, deleteSubscription,
  toggleSubscription, runSubscription, getExecutions, getNextRunTime
} from '@/api/subscriptions'

const subscriptions = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editId = ref(null)
const submitting = ref(false)
const nextRunHint = ref('')
const executionDialogVisible = ref(false)
const executions = ref([])
const executionLoading = ref(false)

const defaultForm = () => ({
  template_id: 1,
  cron_expression: '0 8 * * 1',
  notify_channel: 'feishu',
})
const form = ref(defaultForm())

onMounted(fetchSubscriptions)

async function fetchSubscriptions() {
  loading.value = true
  try {
    subscriptions.value = await listSubscriptions()
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  editId.value = null
  form.value = defaultForm()
  nextRunHint.value = ''
  dialogVisible.value = true
}

function showEditDialog(row) {
  editId.value = row.id
  form.value = {
    template_id: row.template_id,
    cron_expression: row.cron_expression,
    notify_channel: row.notify_channel,
  }
  nextRunHint.value = ''
  dialogVisible.value = true
}

async function checkNextRun() {
  if (!form.value.cron_expression) return
  try {
    const res = await getNextRunTime(form.value.cron_expression)
    nextRunHint.value = res.next_run_at
  } catch {
    nextRunHint.value = '无效的 cron 表达式'
  }
}

async function handleSubmit() {
  if (!form.value.cron_expression) {
    ElMessage.warning('请填写 Cron 表达式')
    return
  }
  submitting.value = true
  try {
    const data = {
      template_id: form.value.template_id,
      cron_expression: form.value.cron_expression,
      notify_channel: form.value.notify_channel,
    }
    if (editId.value) {
      await updateSubscription(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createSubscription(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchSubscriptions()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

async function handleToggle(row) {
  try {
    await toggleSubscription(row.id, !row.is_active)
    ElMessage.success(row.is_active ? '已禁用' : '已启用')
    fetchSubscriptions()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleRunNow(row) {
  try {
    await runSubscription(row.id)
    ElMessage.success('已触发执行')
    fetchSubscriptions()
  } catch {
    ElMessage.error('触发失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除该订阅吗？`, '确认')
    await deleteSubscription(row.id)
    ElMessage.success('已删除')
    fetchSubscriptions()
  } catch {
    // cancelled or error
  }
}

async function showExecutions(row) {
  executionDialogVisible.value = true
  executionLoading.value = true
  try {
    executions.value = await getExecutions(row.id)
  } catch {
    ElMessage.error('加载执行历史失败')
  } finally {
    executionLoading.value = false
  }
}

function statusLabel(s) {
  const map = { pending: '进行中', success: '成功', failed: '失败' }
  return map[s] || s
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
}

.next-run-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #409eff;
}

.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}
</style>
