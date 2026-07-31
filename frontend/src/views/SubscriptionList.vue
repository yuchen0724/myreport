<template>
  <div class="subscriptions">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <h3>查询订阅推送</h3>
            <p>按固定周期推送模板查询或语义指标结果。</p>
          </div>
          <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建订阅</el-button>
        </div>
      </template>

      <el-table :data="subscriptions" v-loading="loading" stripe>
        <el-table-column label="订阅对象" min-width="220">
          <template #default="{ row }">
            <div class="target-cell">
              <el-tag :type="row.subscription_type === 'briefing' ? 'success' : row.semantic_metric_key ? 'warning' : 'primary'" size="small">
                {{ row.subscription_type === 'briefing' ? '经营日报' : row.semantic_metric_key ? '语义指标' : '模板' }}
              </el-tag>
              <span>{{ subscriptionTargetLabel(row) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="查询配置" min-width="180">
          <template #default="{ row }">
            <span v-if="row.subscription_type === 'briefing'">{{ briefingConfigLabel(row.briefing_config) }}</span>
            <span v-else-if="row.semantic_metric_key">{{ semanticQueryLabel(row.semantic_query) }}</span>
            <span v-else>-</span>
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
            {{ formatDate(row.last_run_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
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

    <el-dialog
      v-model="dialogVisible"
      :title="editId ? '编辑订阅' : '新建订阅'"
      width="760px"
      destroy-on-close
    >
      <el-form :model="form" label-width="110px">
        <el-form-item label="订阅类型">
          <el-radio-group v-model="form.subscription_type" :disabled="!!editId">
            <el-radio-button label="template">模板查询</el-radio-button>
            <el-radio-button label="semantic">语义指标</el-radio-button>
            <el-radio-button label="briefing">智能经营日报</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.subscription_type === 'template'" label="查询模板">
          <el-select
            v-model="form.template_id"
            filterable
            :disabled="!!editId"
            placeholder="选择要订阅的模板"
            style="width: 100%"
          >
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="`${template.name || `模板#${template.id}`} (#${template.id})`"
              :value="template.id"
            />
          </el-select>
        </el-form-item>

        <template v-else-if="form.subscription_type === 'semantic'">
          <el-form-item label="语义指标">
            <el-select
              v-model="form.semantic_metric_key"
              filterable
              placeholder="选择要订阅的指标"
              style="width: 100%"
              @change="handleMetricChange"
            >
              <el-option
                v-for="metric in metrics"
                :key="metric.metric_key"
                :label="`${metric.name} (${metric.metric_key})`"
                :value="metric.metric_key"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="维度">
            <el-select
              v-model="form.semantic_query.dimensions"
              multiple
              filterable
              placeholder="留空表示查询总计"
              style="width: 100%"
            >
              <el-option
                v-for="dimension in selectedMetricDimensions"
                :key="dimension"
                :label="dimension"
                :value="dimension"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="时间范围">
            <el-date-picker
              v-model="form.semantic_query.dateRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              unlink-panels
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="过滤条件">
            <div class="filter-list">
              <div
                v-for="(filter, index) in form.semantic_query.filterRows"
                :key="filter.id"
                class="filter-row"
              >
                <el-select v-model="filter.field" placeholder="字段" filterable>
                  <el-option
                    v-for="field in selectedMetricFilterFields"
                    :key="field"
                    :label="field"
                    :value="field"
                  />
                </el-select>
                <el-input v-model="filter.value" placeholder="值" />
                <el-button :icon="Delete" @click="removeFilterRow(index)" />
              </div>
              <el-button :icon="Plus" @click="addFilterRow">添加条件</el-button>
            </div>
          </el-form-item>

          <el-form-item label="最大行数">
            <el-input-number v-model="form.semantic_query.page_size" :min="1" :max="1000" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="日报标题">
            <el-input v-model="form.briefing_config.title" placeholder="智能经营日报" />
          </el-form-item>
          <el-form-item label="经营指标" required>
            <el-select
              v-model="form.briefing_config.metric_keys"
              multiple
              filterable
              :multiple-limit="10"
              placeholder="选择 1-10 个已治理语义指标"
              style="width: 100%"
            >
              <el-option
                v-for="metric in metrics"
                :key="metric.metric_key"
                :label="`${metric.name} (${metric.metric_key})`"
                :value="metric.metric_key"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="统计周期">
            <el-select v-model="form.briefing_config.period" style="width: 100%">
              <el-option label="昨日" value="yesterday" />
              <el-option label="今日" value="today" />
              <el-option label="最近 7 天" value="last_7_days" />
            </el-select>
          </el-form-item>
          <el-form-item label="AI 解读">
            <el-switch v-model="form.briefing_config.include_ai_summary" />
            <span class="field-help">数字由语义指标计算，AI 只负责解读证据。</span>
          </el-form-item>
        </template>

        <el-form-item label="Cron 表达式">
          <el-input v-model="form.cron_expression" placeholder="如：0 8 * * 1">
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

    <el-dialog v-model="executionDialogVisible" title="执行历史" width="700px">
      <el-table :data="executions" v-loading="executionLoading" stripe>
        <el-table-column prop="executed_at" label="执行时间" width="200">
          <template #default="{ row }">
            {{ formatDate(row.executed_at) }}
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import {
  createSubscription,
  deleteSubscription,
  getExecutions,
  getNextRunTime,
  listSubscriptions,
  runSubscription,
  toggleSubscription,
  updateSubscription,
} from '@/api/subscriptions'
import { getSemanticMetrics } from '@/api/semanticMetric'
import { getTemplateList } from '@/api/template'

const subscriptions = ref([])
const templates = ref([])
const metrics = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editId = ref(null)
const submitting = ref(false)
const nextRunHint = ref('')
const executionDialogVisible = ref(false)
const executions = ref([])
const executionLoading = ref(false)
let filterRowSeed = 0

const emptySemanticQuery = () => ({
  dimensions: [],
  dateRange: [],
  filterRows: [],
  page_size: 50,
})

const defaultForm = () => ({
  subscription_type: 'template',
  template_id: null,
  semantic_metric_key: '',
  semantic_query: emptySemanticQuery(),
  briefing_config: {
    title: '智能经营日报',
    metric_keys: [],
    period: 'yesterday',
    include_ai_summary: true,
  },
  cron_expression: '0 8 * * 1',
  notify_channel: 'feishu',
})

const form = ref(defaultForm())

const metricByKey = computed(() => {
  const map = new Map()
  metrics.value.forEach((metric) => map.set(metric.metric_key, metric))
  return map
})

const templateById = computed(() => {
  const map = new Map()
  templates.value.forEach((template) => map.set(template.id, template))
  return map
})

const selectedMetric = computed(() => metricByKey.value.get(form.value.semantic_metric_key))

const selectedMetricDimensions = computed(() => selectedMetric.value?.dimensions || [])

const selectedMetricFilterFields = computed(() => {
  const fields = [...selectedMetricDimensions.value]
  if (selectedMetric.value?.time_column) fields.unshift(selectedMetric.value.time_column)
  return fields
})

onMounted(async () => {
  await Promise.all([fetchSubscriptions(), loadTemplates(), loadMetrics()])
})

async function fetchSubscriptions() {
  loading.value = true
  try {
    subscriptions.value = await listSubscriptions()
  } catch (error) {
    ElMessage.error('加载订阅列表失败')
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  try {
    templates.value = await getTemplateList()
  } catch {
    templates.value = []
  }
}

async function loadMetrics() {
  try {
    metrics.value = await getSemanticMetrics()
  } catch {
    metrics.value = []
  }
}

function showCreateDialog() {
  editId.value = null
  form.value = defaultForm()
  if (templates.value[0]) form.value.template_id = templates.value[0].id
  nextRunHint.value = ''
  dialogVisible.value = true
}

function showEditDialog(row) {
  editId.value = row.id
  const semanticQuery = normalizeSemanticQuery(row.semantic_query || {})
  form.value = {
    subscription_type: row.subscription_type === 'briefing' ? 'briefing' : row.semantic_metric_key ? 'semantic' : 'template',
    template_id: row.template_id || null,
    semantic_metric_key: row.semantic_metric_key || '',
    semantic_query: semanticQuery,
    briefing_config: {
      title: row.briefing_config?.title || '智能经营日报',
      metric_keys: row.briefing_config?.metric_keys || [],
      period: row.briefing_config?.period || 'yesterday',
      include_ai_summary: row.briefing_config?.include_ai_summary !== false,
    },
    cron_expression: row.cron_expression,
    notify_channel: row.notify_channel,
  }
  nextRunHint.value = ''
  dialogVisible.value = true
}

function normalizeSemanticQuery(query) {
  const filters = query.filters || {}
  const filterRows = Object.entries(filters).map(([field, value]) => ({
    id: ++filterRowSeed,
    field,
    value,
  }))
  const dateRange = query.start_time && query.end_time ? [query.start_time, query.end_time] : []
  return {
    dimensions: Array.isArray(query.dimensions) ? query.dimensions : [],
    dateRange,
    filterRows,
    page_size: query.page_size || 50,
  }
}

function handleMetricChange() {
  form.value.semantic_query.dimensions = []
  form.value.semantic_query.filterRows = []
}

function addFilterRow() {
  form.value.semantic_query.filterRows.push({
    id: ++filterRowSeed,
    field: '',
    value: '',
  })
}

function removeFilterRow(index) {
  form.value.semantic_query.filterRows.splice(index, 1)
}

async function checkNextRun() {
  if (!form.value.cron_expression) return
  try {
    const res = await getNextRunTime(form.value.cron_expression)
    nextRunHint.value = res.next_run_at || '无效的 cron 表达式'
  } catch {
    nextRunHint.value = '无效的 cron 表达式'
  }
}

async function handleSubmit() {
  if (!form.value.cron_expression) {
    ElMessage.warning('请填写 Cron 表达式')
    return
  }
  if (form.value.subscription_type === 'template' && !form.value.template_id) {
    ElMessage.warning('请选择查询模板')
    return
  }
  if (form.value.subscription_type === 'semantic' && !form.value.semantic_metric_key) {
    ElMessage.warning('请选择语义指标')
    return
  }
  if (form.value.subscription_type === 'briefing' && !form.value.briefing_config.metric_keys.length) {
    ElMessage.warning('请至少选择一个经营指标')
    return
  }

  submitting.value = true
  try {
    const data = buildSubmitPayload()
    if (editId.value) {
      await updateSubscription(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createSubscription(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchSubscriptions()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

function buildSubmitPayload() {
  const payload = {
    cron_expression: form.value.cron_expression,
    notify_channel: form.value.notify_channel,
  }

  if (form.value.subscription_type === 'template') {
    if (!editId.value) payload.template_id = form.value.template_id
    return payload
  }

  if (form.value.subscription_type === 'briefing') {
    payload.subscription_type = 'briefing'
    payload.briefing_config = form.value.briefing_config
    return payload
  }

  payload.semantic_metric_key = form.value.semantic_metric_key
  payload.semantic_query = buildSemanticQueryPayload()
  return payload
}

function buildSemanticQueryPayload() {
  const filters = {}
  form.value.semantic_query.filterRows.forEach((filter) => {
    if (filter.field && filter.value !== '') filters[filter.field] = filter.value
  })
  const [startTime, endTime] = form.value.semantic_query.dateRange || []
  return {
    dimensions: form.value.semantic_query.dimensions,
    filters,
    start_time: startTime || null,
    end_time: endTime || null,
    page_size: form.value.semantic_query.page_size || 50,
  }
}

async function handleToggle(row) {
  try {
    await toggleSubscription(row.id, !row.is_active)
    ElMessage.success(row.is_active ? '已禁用' : '已启用')
    await fetchSubscriptions()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleRunNow(row) {
  try {
    await runSubscription(row.id)
    ElMessage.success('已触发执行')
    await fetchSubscriptions()
  } catch {
    ElMessage.error('触发失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该订阅吗？', '确认')
    await deleteSubscription(row.id)
    ElMessage.success('已删除')
    await fetchSubscriptions()
  } catch {
    // cancelled or failed
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

function subscriptionTargetLabel(row) {
  if (row.subscription_type === 'briefing') {
    return row.briefing_config?.title || '智能经营日报'
  }
  if (row.semantic_metric_key) {
    return metricByKey.value.get(row.semantic_metric_key)?.name || row.metric_name || row.semantic_metric_key
  }
  return row.template_name || templateById.value.get(row.template_id)?.name || `模板#${row.template_id}`
}

function briefingConfigLabel(config) {
  const metricCount = config?.metric_keys?.length || 0
  const periodMap = { yesterday: '昨日', today: '今日', last_7_days: '最近 7 天' }
  return `${periodMap[config?.period] || '昨日'} / ${metricCount} 个指标`
}

function semanticQueryLabel(query) {
  const dimensions = query?.dimensions || []
  const dimensionText = dimensions.length ? dimensions.join(', ') : '总计'
  const hasDate = query?.start_time && query?.end_time
  return hasDate ? `${dimensionText} / ${query.start_time} 至 ${query.end_time}` : dimensionText
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function statusLabel(status) {
  const map = { pending: '进行中', success: '成功', failed: '失败' }
  return map[status] || status
}
</script>

<style scoped>
.subscriptions {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.card-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}

.card-header p {
  margin: 0;
  color: #667085;
  font-size: 13px;
}

.target-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.next-run-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #409eff;
}
.field-help {
  margin-left: 10px;
  color: #667085;
  font-size: 12px;
}

.filter-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.filter-row {
  display: grid;
  grid-template-columns: minmax(160px, 220px) 1fr 36px;
  gap: 8px;
  width: 100%;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}
</style>
