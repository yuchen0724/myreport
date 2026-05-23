<template>
  <div class="model-compare">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>模型对比训练</h3>
          <p class="subtitle">同一数据源/时间范围，多模型同时训练并对比 MAE、RMSE、R2 等指标</p>
        </div>
      </template>

      <el-form :model="form" label-width="120px" class="compare-form">
        <el-form-item label="数据源">
          <el-select v-model="form.data_source_id" placeholder="选择数据源">
            <el-option v-for="ds in dataSources" :key="ds.id" :label="ds.name" :value="ds.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="对比模型">
          <el-checkbox-group v-model="form.model_types">
            <el-checkbox v-for="mt in modelTypes" :key="mt.value" :value="mt.value" :label="mt.value">
              {{ mt.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="训练天数">
              <el-input-number v-model="form.train_days" :min="30" :max="3650" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="测试天数">
              <el-input-number v-model="form.test_days" :min="7" :max="365" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="验证天数">
              <el-input-number v-model="form.valid_days" :min="7" :max="365" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="表名">
          <el-input v-model="form.table_name" placeholder="如: dwd_sales" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleStart" :loading="submitting" :disabled="form.model_types.length < 2">
            开始对比训练
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 对比结果 -->
      <div v-if="compareResult" class="compare-results">
        <el-divider />
        <div class="results-header">
          <h4>对比结果</h4>
          <div class="results-controls">
            <el-button v-if="compareResult.status === 'running'" size="small" type="primary" @click="pollStatus">
              刷新状态
            </el-button>
            <el-tag :type="compareResult.status === 'completed' ? 'success' : 'warning'" size="small">
              {{ compareResult.status === 'completed' ? '已完成' : '训练中...' }}
            </el-tag>
          </div>
        </div>

        <el-table :data="compareResult.results" stripe>
          <el-table-column prop="model_type" label="模型类型" width="140">
            <template #default="{ row }">
              <el-tag>{{ modelLabel(row.model_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="MAE" width="100">
            <template #default="{ row }">
              {{ formatMetric(row.metrics, 'mae') }}
            </template>
          </el-table-column>
          <el-table-column label="RMSE" width="100">
            <template #default="{ row }">
              {{ formatMetric(row.metrics, 'rmse') }}
            </template>
          </el-table-column>
          <el-table-column label="R2 Score" width="100">
            <template #default="{ row }">
              {{ formatMetric(row.metrics, 'r2') }}
            </template>
          </el-table-column>
          <el-table-column prop="trained_at" label="完成时间" width="180">
            <template #default="{ row }">
              {{ row.trained_at ? new Date(row.trained_at).toLocaleString('zh-CN') : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="error" label="错误信息" min-width="150">
            <template #default="{ row }">
              <span v-if="row.error" class="error-text">{{ row.error }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="优势" width="80">
            <template #default="{ row }">
              <el-tag v-if="isBest(row, 'mae')" type="success" size="small">最低 MAE</el-tag>
              <el-tag v-else-if="isBest(row, 'rmse')" type="warning" size="small">最低 RMSE</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { startCompare, getCompareStatus } from '@/api/modelCompare'
import { getDataSourceList } from '@/api/data_source'

const modelTypes = [
  { value: 'lightgbm', label: 'LightGBM (树模型)' },
  { value: 'prophet', label: 'Prophet (时间序列)' },
  { value: 'naive', label: 'Naive (基准线)' },
  { value: 'sarima', label: 'SARIMA (自回归)' },
]

const dataSources = ref([])
const form = ref({
  data_source_id: null,
  model_types: ['lightgbm', 'prophet'],
  train_days: 365,
  test_days: 30,
  valid_days: 30,
  table_name: 'dwd_sales',
})
const compareResult = ref(null)
const submitting = ref(false)
let pollTimer = null

onMounted(async () => {
  try {
    dataSources.value = await getDataSourceList()
  } catch {
    ElMessage.warning('加载数据源失败')
  }
})

function modelLabel(v) {
  return modelTypes.find(m => m.value === v)?.label || v
}

function statusType(s) {
  const map = { pending: 'info', running: 'warning', training: 'warning', completed: 'success', success: 'success', failed: 'danger' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { pending: '等待中', running: '训练中', training: '训练中', completed: '已完成', success: '已完成', failed: '失败' }
  return map[s] || s
}

function formatMetric(metrics, key) {
  if (!metrics || metrics[key] === undefined || metrics[key] === null) return '-'
  return Number(metrics[key]).toFixed(4)
}

function isBest(row, key) {
  if (!compareResult.value) return false
  const completed = compareResult.value.results.filter(r => r.status === 'completed' && r.metrics && r.metrics[key] !== undefined && r.metrics[key] !== null)
  if (completed.length < 2) return false
  const minVal = Math.min(...completed.map(r => r.metrics[key]))
  return row.metrics && row.metrics[key] === minVal
}

async function handleStart() {
  if (form.value.model_types.length < 2) {
    ElMessage.warning('至少选择2个模型进行对比')
    return
  }
  submitting.value = true
  try {
    const res = await startCompare(form.value)
    compareResult.value = res
    ElMessage.success('对比训练已启动')
    // 开始轮询
    startPolling(res.compare_id)
  } catch (e) {
    ElMessage.error('启动失败')
  } finally {
    submitting.value = false
  }
}

function startPolling(compareId) {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
  pollTimer = setInterval(async () => {
    try {
      const res = await getCompareStatus(compareId)
      compareResult.value = res
      if (res.status === 'completed') {
        clearInterval(pollTimer)
        pollTimer = null
        ElMessage.success('模型对比训练全部完成')
      }
    } catch {
      // ignore polling errors
    }
  }, 5000)
}

async function pollStatus() {
  if (compareResult.value?.compare_id) {
    try {
      const res = await getCompareStatus(compareResult.value.compare_id)
      compareResult.value = res
    } catch {
      ElMessage.error('刷新失败')
    }
  }
}
</script>

<style scoped>
.card-header h3 { margin: 0 0 4px 0; }
.card-header .subtitle { margin: 0; font-size: 13px; color: #909399; }

.compare-form { max-width: 700px; }

.results-header { display: flex; justify-content: space-between; align-items: center; }
.results-header h4 { margin: 0; }

.error-text { color: #f56c6c; font-size: 12px; }
</style>
