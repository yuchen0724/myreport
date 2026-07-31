<!-- frontend/src/views/SqlReviewList.vue -->
<template>
  <div class="sql-review-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>SQL 审核工单</h3>
          <div class="header-actions">
            <el-select v-model="statusFilter" placeholder="全部状态" clearable @change="loadReviews" style="width: 140px">
              <el-option label="待审核" value="pending" />
              <el-option label="已通过" value="approved" />
              <el-option label="已拒绝" value="rejected" />
            </el-select>
            <el-button type="primary" @click="showSubmitDialog">
              <el-icon><Plus /></el-icon> 提交审核
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="reviews" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="template_name" label="模板" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.template_name || `模板#${row.template_id}` }}
          </template>
        </el-table-column>
        <el-table-column prop="sql_content" label="SQL 内容" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <code class="sql-preview">{{ row.sql_content || '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ai_risk_level" label="机器预审" width="110">
          <template #default="{ row }">
            <el-tag :type="riskType(row.ai_risk_level)" size="small">
              {{ riskLabel(row.ai_risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="submitter_name" label="提交人" width="100">
          <template #default="{ row }">
            {{ row.submitter_name || `用户#${row.submitted_by}` }}
          </template>
        </el-table-column>
        <el-table-column prop="reviewer_name" label="审核人" width="100">
          <template #default="{ row }">
            {{ row.reviewer_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="170">
          <template #default="{ row }">
            {{ row.created_at ? formatDate(row.created_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'pending' && isAdmin"
              type="primary" link size="small"
              @click="handleAiReview(row)"
            >重新预审</el-button>
            <el-button
              v-if="row.status === 'pending' && isAdmin"
              type="success" link size="small"
              @click="showReviewDialog(row, 'approved')"
            >通过</el-button>
            <el-button
              v-if="row.status === 'pending' && isAdmin"
              type="danger" link size="small"
              @click="showReviewDialog(row, 'rejected')"
            >拒绝</el-button>
            <el-button
              v-if="row.status === 'pending' && row.submitted_by === currentUserId"
              type="warning" link size="small"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @size-change="loadReviews"
          @current-change="loadReviews"
        />
      </div>
    </el-card>

    <!-- 提交审核对话框 -->
    <el-dialog v-model="submitDialogVisible" title="提交 SQL 审核" width="600px">
      <el-form :model="submitForm" label-width="100px">
        <el-form-item label="模板 ID" required>
          <el-input-number v-model="submitForm.template_id" :min="1" />
        </el-form-item>
        <el-form-item label="SQL 内容">
          <el-input
            v-model="submitForm.sql_content"
            type="textarea"
            :rows="6"
            placeholder="请输入待审核的 SQL 语句..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="submitDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>

    <!-- 审核操作对话框 -->
    <el-dialog v-model="reviewDialogVisible" :title="reviewAction === 'approved' ? '审核通过' : '审核拒绝'" width="500px">
      <p>确认{{ reviewAction === 'approved' ? '通过' : '拒绝' }}工单 #{{ reviewTarget?.id }} 吗？</p>
      <el-input
        v-model="reviewComment"
        type="textarea"
        :rows="3"
        placeholder="审核意见（可选）"
      />
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button
          :type="reviewAction === 'approved' ? 'success' : 'danger'"
          @click="handleReview"
          :loading="reviewing"
        >{{ reviewAction === 'approved' ? '通过' : '拒绝' }}</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="审核工单详情" width="650px">
      <el-descriptions :column="2" border v-if="detailRow">
        <el-descriptions-item label="工单 ID">{{ detailRow.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(detailRow.status)">{{ statusLabel(detailRow.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模板">{{ detailRow.template_name || `模板#${detailRow.template_id}` }}</el-descriptions-item>
        <el-descriptions-item label="提交人">{{ detailRow.submitter_name || `用户#${detailRow.submitted_by}` }}</el-descriptions-item>
        <el-descriptions-item label="审核人">{{ detailRow.reviewer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审核时间">{{ detailRow.reviewed_at ? formatDate(detailRow.reviewed_at) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ detailRow.created_at ? formatDate(detailRow.created_at) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="审核意见">{{ detailRow.review_comment || '-' }}</el-descriptions-item>
        <el-descriptions-item label="机器风险">
          <el-tag :type="riskType(detailRow.ai_risk_level)">{{ riskLabel(detailRow.ai_risk_level) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="预审建议">{{ detailRow.ai_review?.recommendation || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SQL 内容" :span="2">
          <pre class="sql-block">{{ detailRow.sql_content || '无' }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="机器预审发现" :span="2">
          <el-alert
            v-for="finding in detailRow.ai_review?.findings || []"
            :key="finding.code"
            :title="finding.title"
            :type="finding.severity === 'high' ? 'error' : riskType(finding.severity)"
            :description="`${finding.detail} 建议：${finding.suggestion}`"
            show-icon
            :closable="false"
            class="review-finding"
          />
          <el-empty v-if="!(detailRow.ai_review?.findings || []).length" description="未发现规则风险" :image-size="56" />
        </el-descriptions-item>
        <el-descriptions-item v-if="detailRow.ai_review?.ai_summary" label="AI 说明" :span="2">
          <div class="ai-summary">{{ detailRow.ai_review.ai_summary }}</div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useUserStore } from '@/store'
import {
  listReviews,
  getReview,
  createReview,
  reviewSql,
  refreshAiReview,
  deleteReview,
} from '@/api/sqlReviews'

const userStore = useUserStore()
const isAdmin = computed(() => {
  return userStore.roles && userStore.roles.includes('admin')
})
const currentUserId = computed(() => userStore.userId)

// 列表状态
const reviews = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')

// 提交对话框
const submitDialogVisible = ref(false)
const submitting = ref(false)
const submitForm = ref({ template_id: 1, sql_content: '' })

// 审核对话框
const reviewDialogVisible = ref(false)
const reviewing = ref(false)
const reviewTarget = ref(null)
const reviewAction = ref('approved')
const reviewComment = ref('')

// 详情对话框
const detailDialogVisible = ref(false)
const detailRow = ref(null)

onMounted(() => loadReviews())

async function loadReviews() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await listReviews(params)
    reviews.value = res.items || []
    total.value = res.total || 0
  } catch {
    ElMessage.error('加载审核列表失败')
  } finally {
    loading.value = false
  }
}

function formatDate(d) {
  return new Date(d).toLocaleString('zh-CN')
}

function statusType(s) {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }
  return map[s] || s
}

function riskType(s) {
  const map = { low: 'success', medium: 'warning', high: 'danger' }
  return map[s] || 'info'
}

function riskLabel(s) {
  const map = { low: '低风险', medium: '中风险', high: '高风险' }
  return map[s] || '未预审'
}

// ---- 提交审核 ----
function showSubmitDialog() {
  submitForm.value = { template_id: 1, sql_content: '' }
  submitDialogVisible.value = true
}

async function handleSubmit() {
  if (!submitForm.value.template_id) {
    ElMessage.warning('请填写模板 ID')
    return
  }
  submitting.value = true
  try {
    await createReview(submitForm.value)
    ElMessage.success('审核工单已提交')
    submitDialogVisible.value = false
    loadReviews()
  } catch {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

// ---- 审核操作 ----
function showReviewDialog(row, action) {
  reviewTarget.value = row
  reviewAction.value = action
  reviewComment.value = ''
  reviewDialogVisible.value = true
}

async function handleReview() {
  reviewing.value = true
  try {
    await reviewSql(reviewTarget.value.id, {
      status: reviewAction.value,
      review_comment: reviewComment.value || undefined,
    })
    ElMessage.success(reviewAction.value === 'approved' ? '已通过' : '已拒绝')
    reviewDialogVisible.value = false
    loadReviews()
  } catch {
    ElMessage.error('审核操作失败')
  } finally {
    reviewing.value = false
  }
}

async function handleAiReview(row) {
  try {
    const review = await refreshAiReview(row.id)
    ElMessage.success('机器预审已更新')
    detailRow.value = review
    detailDialogVisible.value = true
    loadReviews()
  } catch {
    ElMessage.error('机器预审失败')
  }
}

// ---- 删除 ----
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定要删除该审核工单吗？', '提示', { type: 'warning' })
    await deleteReview(row.id)
    ElMessage.success('已删除')
    loadReviews()
  } catch {
    // cancelled or error
  }
}

// ---- 详情 ----
function showDetail(row) {
  detailRow.value = row
  detailDialogVisible.value = true
}
</script>

<style scoped>
.sql-review-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header h3 {
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.sql-preview {
  font-family: monospace;
  font-size: 12px;
  color: #606266;
  max-width: 300px;
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sql-block {
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  margin: 0;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.review-finding {
  margin-bottom: 8px;
}
.ai-summary {
  white-space: pre-wrap;
  line-height: 1.7;
}
</style>
