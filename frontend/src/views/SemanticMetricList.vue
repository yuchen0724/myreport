<template>
  <div class="semantic-metric-page">
    <div class="page-toolbar">
      <div>
        <h2>语义指标</h2>
        <p>维护统一指标定义，并按维度预览查询 SQL。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建指标</el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="metrics" border>
        <el-table-column prop="metric_key" label="指标 Key" min-width="140" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="metric_expression" label="聚合表达式" min-width="150" />
        <el-table-column prop="data_source_id" label="数据源" width="90" />
        <el-table-column prop="time_column" label="时间字段" width="130" />
        <el-table-column label="维度" min-width="180">
          <template #default="{ row }">
            <el-tag
              v-for="dimension in row.dimensions"
              :key="dimension"
              size="small"
              class="dimension-tag"
            >
              {{ dimension }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="View" @click="openQueryDrawer(row)">查询</el-button>
            <el-button size="small" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="formDialogVisible"
      :title="editingMetric ? '编辑指标' : '新建指标'"
      width="760px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="指标 Key" prop="metric_key">
              <el-input v-model="form.metric_key" placeholder="gmv" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" placeholder="成交金额" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="数据源" prop="data_source_id">
              <el-select v-model="form.data_source_id" placeholder="选择数据源" filterable>
                <el-option
                  v-for="source in dataSources"
                  :key="source.id"
                  :label="`${source.name} (${source.type})`"
                  :value="source.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时间字段" prop="time_column">
              <el-input v-model="form.time_column" placeholder="biz_date" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="聚合表达式" prop="metric_expression">
          <el-input v-model="form.metric_expression" placeholder="SUM(amount)" />
        </el-form-item>

        <el-form-item label="维度字段">
          <el-select
            v-model="form.dimensions"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入字段名后回车"
          />
        </el-form-item>

        <el-form-item label="基础 SQL" prop="base_sql">
          <el-input v-model="form.base_sql" type="textarea" :rows="7" />
        </el-form-item>

        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="queryDrawerVisible"
      :title="activeMetric ? `${activeMetric.name} 查询` : '指标查询'"
      size="56%"
    >
      <div v-if="activeMetric" class="query-drawer">
        <el-form label-width="90px">
          <el-form-item label="维度">
            <el-select v-model="queryForm.dimensions" multiple placeholder="默认全部维度">
              <el-option
                v-for="dimension in activeMetric.dimensions"
                :key="dimension"
                :label="dimension"
                :value="dimension"
              />
            </el-select>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="24">
              <el-form-item label="时间范围">
                <el-date-picker
                  v-model="queryForm.dateRange"
                  type="daterange"
                  value-format="YYYY-MM-DD"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  unlink-panels
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="过滤条件">
            <div class="filter-list">
              <div
                v-for="(filter, index) in queryForm.filterRows"
                :key="filter.id"
                class="filter-row"
              >
                <el-select v-model="filter.field" placeholder="字段" filterable>
                  <el-option
                    v-for="field in filterFields"
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
          <el-form-item label="分页">
            <div class="pagination-controls">
              <el-input-number v-model="queryForm.page" :min="1" />
              <el-input-number v-model="queryForm.page_size" :min="1" :max="1000" />
              <el-button :icon="DocumentChecked" :loading="previewing" @click="handlePreview">预览 SQL</el-button>
              <el-button type="primary" :icon="Search" :loading="querying" @click="handleExecute">执行查询</el-button>
            </div>
          </el-form-item>
        </el-form>

        <el-input
          v-model="previewSql"
          type="textarea"
          :rows="6"
          readonly
          class="sql-preview"
          placeholder="SQL 预览会显示在这里"
        />

        <div v-if="queryResult" class="result-section">
          <div class="result-toolbar">
            <span>共 {{ queryResult.total }} 行</span>
            <div class="result-actions">
              <el-button :icon="Monitor" @click="openSaveWidgetDialog">保存到看板</el-button>
              <el-button :icon="Download" @click="exportCsv">导出 CSV</el-button>
            </div>
          </div>
          <div class="chart-panel">
            <div v-if="singleMetricValue !== null" class="single-metric">
              <span class="single-metric-label">{{ activeMetric.name }}</span>
              <strong>{{ singleMetricValue }}</strong>
            </div>
            <div v-else ref="chartRef" class="metric-chart"></div>
          </div>
          <el-table :data="queryRows" border class="result-table">
            <el-table-column
              v-for="column in queryResult.columns"
              :key="column"
              :prop="column"
              :label="column"
              min-width="140"
            />
          </el-table>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="saveWidgetDialogVisible" title="保存到看板" width="460px">
      <el-form label-width="90px">
        <el-form-item label="布局">
          <el-select v-model="selectedLayoutId" placeholder="选择布局" filterable>
            <el-option
              v-for="layout in layouts"
              :key="layout.id"
              :label="layout.name"
              :value="layout.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="组件标题">
          <el-input v-model="widgetTitle" />
        </el-form-item>
        <el-form-item label="图表类型">
          <el-radio-group v-model="widgetChartType">
            <el-radio-button label="bar">柱状图</el-radio-button>
            <el-radio-button label="line">折线图</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveWidgetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingWidget" @click="saveToDashboard">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, DocumentChecked, Download, Edit, Monitor, Plus, Search, View } from '@element-plus/icons-vue'
import { getDataSourceList } from '@/api/data_source'
import { createLayout, createWidget, getLayoutList } from '@/api/dashboard'
import echarts from '@/utils/echarts'
import {
  createSemanticMetric,
  deleteSemanticMetric,
  executeSemanticMetricQuery,
  getSemanticMetrics,
  previewSemanticMetricQuery,
  updateSemanticMetric,
} from '@/api/semanticMetric'

const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const querying = ref(false)
const savingWidget = ref(false)
const metrics = ref([])
const dataSources = ref([])
const layouts = ref([])
const formDialogVisible = ref(false)
const queryDrawerVisible = ref(false)
const saveWidgetDialogVisible = ref(false)
const editingMetric = ref(null)
const activeMetric = ref(null)
const formRef = ref(null)
const chartRef = ref(null)
const previewSql = ref('')
const queryResult = ref(null)
const selectedLayoutId = ref(null)
const widgetTitle = ref('')
const widgetChartType = ref('bar')
let filterRowSeed = 0
let chartInstance = null

const emptyForm = () => ({
  metric_key: '',
  name: '',
  description: '',
  data_source_id: null,
  base_sql: 'SELECT * FROM your_table',
  metric_expression: 'COUNT(*)',
  dimensions: [],
  time_column: 'biz_date',
  is_active: true,
})

const form = reactive(emptyForm())
const queryForm = reactive({
  metric_key: '',
  dateRange: [],
  dimensions: [],
  filterRows: [],
  page: 1,
  page_size: 50,
})

const rules = {
  metric_key: [{ required: true, message: '请输入指标 Key', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  data_source_id: [{ required: true, message: '请选择数据源', trigger: 'change' }],
  metric_expression: [{ required: true, message: '请输入聚合表达式', trigger: 'blur' }],
  time_column: [{ required: true, message: '请输入时间字段', trigger: 'blur' }],
  base_sql: [{ required: true, message: '请输入基础 SQL', trigger: 'blur' }],
}

const queryRows = computed(() => {
  if (!queryResult.value) return []
  return queryResult.value.rows.map((row) => {
    const item = {}
    queryResult.value.columns.forEach((column, index) => {
      item[column] = row[index]
    })
    return item
  })
})

const filterFields = computed(() => {
  if (!activeMetric.value) return []
  return [activeMetric.value.time_column, ...(activeMetric.value.dimensions || [])]
})

const singleMetricValue = computed(() => {
  if (!queryResult.value || queryResult.value.columns.length !== 1) return null
  if (queryResult.value.columns[0] !== 'metric_value') return null
  return queryResult.value.rows[0]?.[0] ?? null
})

const resetForm = () => {
  Object.assign(form, emptyForm())
}

const loadMetrics = async () => {
  loading.value = true
  try {
    metrics.value = await getSemanticMetrics()
  } finally {
    loading.value = false
  }
}

const loadDataSources = async () => {
  dataSources.value = await getDataSourceList()
}

const loadLayouts = async () => {
  layouts.value = await getLayoutList()
}

const openCreateDialog = () => {
  editingMetric.value = null
  resetForm()
  formDialogVisible.value = true
}

const openEditDialog = (row) => {
  editingMetric.value = row
  Object.assign(form, {
    metric_key: row.metric_key,
    name: row.name,
    description: row.description || '',
    data_source_id: row.data_source_id,
    base_sql: row.base_sql,
    metric_expression: row.metric_expression || 'COUNT(*)',
    dimensions: [...(row.dimensions || [])],
    time_column: row.time_column,
    is_active: row.is_active,
  })
  formDialogVisible.value = true
}

const submitForm = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = {
      ...form,
      description: form.description || null,
    }
    if (editingMetric.value) {
      await updateSemanticMetric(editingMetric.value.id, payload)
      ElMessage.success('指标已更新')
    } else {
      await createSemanticMetric(payload)
      ElMessage.success('指标已创建')
    }
    formDialogVisible.value = false
    await loadMetrics()
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定删除指标 ${row.metric_key} 吗？`, '删除指标', { type: 'warning' })
  await deleteSemanticMetric(row.id)
  ElMessage.success('指标已删除')
  await loadMetrics()
}

const openQueryDrawer = (row) => {
  activeMetric.value = row
  queryForm.metric_key = row.metric_key
  queryForm.dateRange = []
  queryForm.dimensions = [...(row.dimensions || [])]
  queryForm.filterRows = []
  queryForm.page = 1
  queryForm.page_size = 50
  previewSql.value = ''
  queryResult.value = null
  disposeChart()
  queryDrawerVisible.value = true
}

const addFilterRow = () => {
  queryForm.filterRows.push({
    id: ++filterRowSeed,
    field: '',
    value: '',
  })
}

const removeFilterRow = (index) => {
  queryForm.filterRows.splice(index, 1)
}

const buildQueryPayload = () => {
  const filters = {}
  queryForm.filterRows.forEach((filter) => {
    if (filter.field && filter.value !== '') {
      filters[filter.field] = filter.value
    }
  })
  const [startTime, endTime] = queryForm.dateRange || []
  return {
    metric_key: queryForm.metric_key,
    start_time: startTime || null,
    end_time: endTime || null,
    dimensions: queryForm.dimensions,
    filters,
    page: queryForm.page,
    page_size: queryForm.page_size,
  }
}

const handlePreview = async () => {
  previewing.value = true
  try {
    const preview = await previewSemanticMetricQuery(buildQueryPayload())
    previewSql.value = preview.sql
  } catch (error) {
    ElMessage.error('SQL 预览失败')
  } finally {
    previewing.value = false
  }
}

const handleExecute = async () => {
  querying.value = true
  try {
    const result = await executeSemanticMetricQuery(buildQueryPayload())
    queryResult.value = result.query
    previewSql.value = result.query?.sql || previewSql.value
    await nextTick()
    renderChart()
  } catch (error) {
    ElMessage.error('查询执行失败')
  } finally {
    querying.value = false
  }
}

const disposeChart = () => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

const renderChart = () => {
  if (!queryResult.value || singleMetricValue.value !== null || !chartRef.value) {
    disposeChart()
    return
  }

  const columns = queryResult.value.columns
  const metricIndex = columns.indexOf('metric_value')
  if (metricIndex === -1) {
    disposeChart()
    return
  }

  const dimensionIndex = columns.findIndex((column) => column !== 'metric_value')
  if (dimensionIndex === -1) {
    disposeChart()
    return
  }

  const labels = queryResult.value.rows.map((row) => String(row[dimensionIndex] ?? ''))
  const values = queryResult.value.rows.map((row) => Number(row[metricIndex] ?? 0))

  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 20, top: 28, bottom: 64 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { rotate: labels.length > 6 ? 30 : 0 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: activeMetric.value?.name || 'metric_value',
        type: 'bar',
        data: values,
        barMaxWidth: 42,
        itemStyle: { color: '#409eff' },
      },
    ],
  }, true)
  chartInstance.resize()
}

const handleResize = () => {
  chartInstance?.resize()
}

const escapeCsvValue = (value) => {
  if (value === null || value === undefined) return ''
  const text = String(value)
  if (/[",\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`
  return text
}

const exportCsv = () => {
  if (!queryResult.value) return
  const header = queryResult.value.columns.map(escapeCsvValue).join(',')
  const body = queryRows.value
    .map((row) => queryResult.value.columns.map((column) => escapeCsvValue(row[column])).join(','))
    .join('\n')
  const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${queryForm.metric_key || 'semantic_metric'}_result.csv`
  link.click()
  URL.revokeObjectURL(url)
}

const getChartDimensionColumn = () => {
  if (!queryResult.value) return ''
  return queryResult.value.columns.find((column) => column !== 'metric_value') || ''
}

const openSaveWidgetDialog = async () => {
  if (!queryResult.value) return
  const dimensionColumn = getChartDimensionColumn()
  if (!dimensionColumn) {
    ElMessage.warning('当前结果没有维度列，暂不能保存为图表组件')
    return
  }
  if (!layouts.value.length) {
    const layout = await createLayout({ name: '语义指标看板', is_default: false })
    layouts.value = [layout]
  }
  selectedLayoutId.value = selectedLayoutId.value || layouts.value[0]?.id
  widgetTitle.value = activeMetric.value?.name || queryForm.metric_key
  widgetChartType.value = 'bar'
  saveWidgetDialogVisible.value = true
}

const saveToDashboard = async () => {
  if (!selectedLayoutId.value) {
    ElMessage.warning('请选择看板布局')
    return
  }
  const dimensionColumn = getChartDimensionColumn()
  if (!dimensionColumn) {
    ElMessage.warning('当前结果没有维度列')
    return
  }

  savingWidget.value = true
  try {
    await createWidget(selectedLayoutId.value, {
      widget_type: 'chart',
      widget_subtype: '__semantic_metric__',
      title: widgetTitle.value || activeMetric.value?.name || queryForm.metric_key,
      grid_w: 6,
      grid_h: 4,
      extra_config: {
        semanticMetricQuery: buildQueryPayload(),
        chartSubType: widgetChartType.value,
        chartTitle: widgetTitle.value || activeMetric.value?.name || queryForm.metric_key,
        xAxis: dimensionColumn,
        yAxis: 'metric_value',
      },
    })
    ElMessage.success('已保存到看板')
    saveWidgetDialogVisible.value = false
  } finally {
    savingWidget.value = false
  }
}

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  await Promise.all([loadMetrics(), loadDataSources(), loadLayouts()])
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeChart()
})

watch(queryDrawerVisible, (visible) => {
  if (!visible) disposeChart()
})
</script>

<style scoped>
.semantic-metric-page {
  padding: 20px;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-toolbar h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
}

.page-toolbar p {
  margin: 0;
  color: #667085;
  font-size: 13px;
}

.table-card {
  border-radius: 6px;
}

.dimension-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}

.query-drawer {
  padding-right: 8px;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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

.sql-preview {
  margin: 8px 0 16px;
}

.result-section {
  margin-top: 12px;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #667085;
  font-size: 13px;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-panel {
  min-height: 220px;
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
}

.metric-chart {
  width: 100%;
  height: 260px;
}

.single-metric {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.single-metric-label {
  color: #667085;
  font-size: 14px;
}

.single-metric strong {
  color: #101828;
  font-size: 34px;
  line-height: 1.2;
  font-weight: 700;
}

.result-table {
  margin-top: 12px;
}
</style>
