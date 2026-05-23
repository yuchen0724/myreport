<template>
  <div class="scheduled-reports">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>定时报表管理</h3>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon> 新建定时报表
          </el-button>
        </div>
      </template>

      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="name" label="报表名称" min-width="150" />
        <el-table-column prop="cron_expression" label="Cron 表达式" width="160" />
        <el-table-column prop="output_format" label="格式" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.output_format }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="recipients" label="收件人" width="150">
          <template #default="{ row }">
            {{ (row.recipients || []).map(r => r.email || `���户#${r.user_id}`).join(', ') || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="next_run_at" label="下次执行" width="180">
          <template #default="{ row }">
            {{ row.next_run_at ? new Date(row.next_run_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="上次执行" width="180">
          <template #default="{ row }">
            {{ row.last_run_at ? new Date(row.last_run_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="toggleEnabled(row)">
              {{ row.enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="handleRunNow(row)">立即执行</el-button>
            <el-button size="small" @click="showDeliveries(row)">历史</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑定时报表' : '新建定时报表'" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="报表名称">
          <el-input v-model="form.name" placeholder="如：周销售汇总报表" />
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
        <el-form-item label="输出格式">
          <el-radio-group v-model="form.output_format">
            <el-radio value="excel">Excel</el-radio>
            <el-radio value="pdf">PDF</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="收件人">
          <div v-for="(r, idx) in form.recipients" :key="idx" class="recipient-row">
            <el-input v-model="r.email" placeholder="邮箱地址" style="width: 200px" />
            <el-button @click="removeRecipient(idx)">移除</el-button>
          </div>
          <el-button size="small" @click="form.recipients.push({ email: '' })">+ 添加收件人</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 投递历史对话框 -->
    <el-dialog v-model="deliveryDialogVisible" title="报表投递历史" width="700px">
      <el-table :data="deliveries" v-loading="deliveryLoading" stripe>
        <el-table-column prop="generated_at" label="生成时间" width="200">
          <template #default="{ row }">
            {{ row.generated_at ? new Date(row.generated_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="150" />
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
  listReports, createReport, updateReport, deleteReport,
  toggleReport, runNow, getDeliveries, getNextRunTime
} from '@/api/scheduledReports'

const reports = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editId = ref(null)
const submitting = ref(false)
const nextRunHint = ref('')
const deliveryDialogVisible = ref(false)
const deliveries = ref([])
const deliveryLoading = ref(false)

const defaultForm = () => ({
  name: '',
  cron_expression: '',
  output_format: 'excel',
  recipients: [{ email: '' }],
  parameters: {},
})
const form = ref(defaultForm())

onMounted(fetchReports)

async function fetchReports() {
  loading.value = true
  try {
    reports.value = await listReports()
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

async function checkNextRun() {
  if (!form.value.cron_expression) return
  try {
    const res = await getNextRunTime(form.value.cron_expression)
    nextRunHint.value = res.next_run_at
  } catch {
    nextRunHint.value = '无效的 cron 表达式'
  }
}

function removeRecipient(idx) {
  form.value.recipients.splice(idx, 1)
}

async function handleSubmit() {
  if (!form.value.name || !form.value.cron_expression) {
    ElMessage.warning('请填写报表名称和 Cron 表达式')
    return
  }
  submitting.value = true
  try {
    const data = { ...form.value }
    if (data.recipients.length === 1 && !data.recipients[0].email) {
      data.recipients = []
    }
    if (editId.value) {
      await updateReport(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createReport(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchReports()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

async function toggleEnabled(row) {
  try {
    await toggleReport(row.id, !row.enabled)
    ElMessage.success(row.enabled ? '已禁用' : '已启用')
    fetchReports()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleRunNow(row) {
  try {
    await runNow(row.id)
    ElMessage.success('已触发执行')
    fetchReports()
  } catch {
    ElMessage.error('触发失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除定时报表「${row.name}」吗？`, '确认')
    await deleteReport(row.id)
    ElMessage.success('已删除')
    fetchReports()
  } catch {
    // cancelled or error
  }
}

async function showDeliveries(row) {
  deliveryDialogVisible.value = true
  deliveryLoading.value = true
  try {
    deliveries.value = await getDeliveries(row.id)
  } catch {
    ElMessage.error('加载投递历史失败')
  } finally {
    deliveryLoading.value = false
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

.recipient-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}
</style>
