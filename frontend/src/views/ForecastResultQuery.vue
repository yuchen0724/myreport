<template>
  <div class="forecast-result-query">
    <el-card>
      <template #header>
        <span>预测结果查询</span>
      </template>

      <el-form :inline="true" label-width="90px">
        <el-row :gutter="16" style="width: 100%">
          <el-col :span="8">
            <el-form-item label="数据源">
              <el-select
                v-model="filters.dataSourceId"
                placeholder="请选择数据源"
                clearable
                filterable
                style="width: 100%"
                @change="onDataSourceChange"
              >
                <el-option
                  v-for="ds in dataSources"
                  :key="ds.id"
                  :label="ds.name"
                  :value="ds.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="模型">
              <el-select
                v-model="filters.modelId"
                placeholder="全部模型"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="m in models"
                  :key="m.model_id"
                  :label="`模型 #${m.model_id} (${formatDate(m.trained_at)})`"
                  :value="m.model_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="门店编码">
              <el-input
                v-model="filters.storeCode"
                placeholder="输入门店编码"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="width: 100%">
          <el-col :span="8">
            <el-form-item label="商品编码">
              <el-input
                v-model="filters.matnr"
                placeholder="输入商品编码"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预测日期">
              <el-date-picker
                v-model="filters.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="排序">
              <el-select v-model="filters.sortBy" style="width: 100%">
                <el-option label="预测日期" value="forecast_date" />
                <el-option label="预测值" value="predicted_value" />
                <el-option label="门店编码" value="store_code" />
                <el-option label="商品编码" value="matnr" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="方向">
              <el-select v-model="filters.sortOrder" style="width: 100%">
                <el-option label="升序" value="asc" />
                <el-option label="降序" value="desc" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row style="width: 100%; margin-top: 8px">
          <el-form-item>
            <el-button type="primary" @click="handleSearch" :loading="loading">
              查询
            </el-button>
            <el-button @click="handleReset">重置</el-button>
            <el-button
              type="success"
              @click="handleExport"
              :loading="exporting"
              :disabled="!hasData"
            >
              导出 Excel
            </el-button>
          </el-form-item>
        </el-row>
      </el-form>
    </el-card>

    <!-- 预测趋势图 -->
    <el-card class="chart-card" v-if="hasData && isChartMode" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>预测趋势图</span>
          <el-radio-group v-model="chartMode" size="small">
            <el-radio-button value="line">折线图</el-radio-button>
            <el-radio-button value="area">面积图</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div ref="chartRef" class="forecast-chart" />
    </el-card>

    <el-card style="margin-top: 16px">
      <div class="result-header">
        <span v-if="total > 0">共 {{ total }} 条记录</span>
        <span v-else>&nbsp;</span>
      </div>

      <el-table
        :data="forecastData"
        v-loading="loading"
        empty-text="暂无匹配的预测结果"
        border
        stripe
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="store_code" label="门店编码" width="120" show-overflow-tooltip />
        <el-table-column prop="matnr" label="商品编码" width="160" show-overflow-tooltip />
        <el-table-column prop="forecast_date" label="预测日期" width="130" />
        <el-table-column prop="predicted_value" label="预测值" width="140">
          <template #default="{ row }">
            {{ row.predicted_value.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="lower_bound" label="下限" width="140">
          <template #default="{ row }">
            {{ row.lower_bound != null ? row.lower_bound.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="upper_bound" label="上限" width="140">
          <template #default="{ row }">
            {{ row.upper_bound != null ? row.upper_bound.toFixed(2) : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          v-model:page-size="pageSize"
          v-model:current-page="page"
          :page-sizes="[20, 50, 100]"
          @current-change="loadForecast"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getDataSourceList } from '@/api/data_source'
import { getForecast, getMyTrainTasks, exportForecastExcel } from '@/api/prediction'
import * as echarts from 'echarts'

const dataSources = ref([])
const models = ref([])
const loading = ref(false)
const exporting = ref(false)
const forecastData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  dataSourceId: null,
  modelId: null,
  storeCode: '',
  matnr: '',
  dateRange: null,
  sortBy: 'forecast_date',
  sortOrder: 'asc',
})

const hasData = computed(() => forecastData.value.length > 0)

// 图表相关
const chartRef = ref(null)
const chartMode = ref('line')
const isChartMode = computed(() => chartRef.value !== null && forecastData.value.length > 0)
let chartInstance = null
let resizeHandler = null

function formatDate(iso) {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}

async function loadDataSources() {
  try {
    const res = await getDataSourceList()
    dataSources.value = Array.isArray(res) ? res : (res.data || [])
  } catch {
    ElMessage.error('加载数据源失败')
  }
}

async function loadModels() {
  if (!filters.dataSourceId) {
    models.value = []
    return
  }
  try {
    const res = await getMyTrainTasks(false)
    const list = Array.isArray(res) ? res : (res.data || [])
    models.value = list.filter(m => m.status === 'ready' && m.data_source_id === filters.dataSourceId)
    if (filters.modelId && !models.value.some(m => m.model_id === filters.modelId)) {
      filters.modelId = null
    }
  } catch {
    models.value = []
  }
}

function onDataSourceChange() {
  filters.modelId = null
  loadModels()
}

function buildParams() {
  const params = {
    data_source_id: filters.dataSourceId,
    page: page.value,
    page_size: pageSize.value,
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
  }
  if (filters.modelId) params.model_id = filters.modelId
  if (filters.storeCode) params.store_code = filters.storeCode.trim()
  if (filters.matnr) params.matnr = filters.matnr.trim()
  if (filters.dateRange && filters.dateRange.length === 2) {
    params.start_date = filters.dateRange[0]
    params.end_date = filters.dateRange[1]
  }
  return params
}

async function loadForecast() {
  if (!filters.dataSourceId) {
    ElMessage.warning('请先选择数据源')
    return
  }
  loading.value = true
  try {
    const res = await getForecast(buildParams())
    const data = res?.items || res?.data?.items || []
    forecastData.value = data
    total.value = res?.total ?? 0
  } catch (e) {
    ElMessage.error('查询失败: ' + (e.message || '未知错误'))
    forecastData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadForecast().then(() => {
    nextTick(() => renderChart())
  })
}

function handleReset() {
  filters.dataSourceId = null
  filters.modelId = null
  filters.storeCode = ''
  filters.matnr = ''
  filters.dateRange = null
  filters.sortBy = 'forecast_date'
  filters.sortOrder = 'asc'
  page.value = 1
  pageSize.value = 20
  forecastData.value = []
  total.value = 0
  models.value = []
  destroyChart()
}

function onSizeChange() {
  page.value = 1
  loadForecast().then(() => {
    nextTick(() => renderChart())
  })
}

function handleSortChange({ prop, order }) {
  if (prop) {
    filters.sortBy = prop
    filters.sortOrder = order === 'descending' ? 'desc' : 'asc'
    handleSearch()
  }
}

// ---- 图表渲染 ----
function getSeriesKey(row) {
  return `${row.store_code}@${row.matnr}`
}

function renderChart() {
  const data = forecastData.value
  if (!data.length || !chartRef.value) return

  // 按 store_code@matnr 分组
  const groups = {}
  for (const row of data) {
    const key = getSeriesKey(row)
    if (!groups[key]) groups[key] = []
    groups[key].push(row)
  }

  const keys = Object.keys(groups)
  const isSingle = keys.length === 1

  // 颜色池
  const colorPalette = [
    '#5470c6', '#91cc75', '#fac858', '#ee6666',
    '#73c0de', '#3ba272', '#fc8452', '#9a60b4',
    '#ea7ccc', '#4a90d9',
  ]

  const series = []
  const legendData = []

  keys.forEach((key, idx) => {
    const items = groups[key]
    const color = colorPalette[idx % colorPalette.length]
    const sorted = [...items].sort(
      (a, b) => a.forecast_date.localeCompare(b.forecast_date)
    )
    const dates = sorted.map(r => r.forecast_date)
    const values = sorted.map(r => r.predicted_value)

    const label = isSingle ? '预测值' : key

    if (isSingle) {
      // 单门店+单商品：折线 + 置信区间
      const lower = sorted.map(r =>
        r.lower_bound != null ? r.lower_bound : null
      )
      const upper = sorted.map(r =>
        r.upper_bound != null ? r.upper_bound : null
      )
      const hasConfidence = lower.some(v => v != null)

      if (hasConfidence) {
        // 置信区间面积图
        const confidenceArea = []
        for (let i = 0; i < sorted.length; i++) {
          confidenceArea.push([
            dates[i],
            upper[i] != null ? upper[i] : values[i],
            lower[i] != null ? lower[i] : values[i],
          ])
        }

        series.push({
          name: '置信区间',
          type: 'line',
          data: values,
          smooth: true,
          symbol: 'none',
          lineStyle: { opacity: 0 },
          z: 1,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}40` },
              { offset: 1, color: `${color}10` },
            ]),
          },
          tooltip: {
            formatter: function (params) {
              const idx = params.dataIndex
              const item = sorted[idx]
              return [
                `<div style="font-size:12px;color:#999">${item.forecast_date}</div>`,
                `<div>预测值: <b>${item.predicted_value.toFixed(2)}</b></div>`,
                `<div>下限: ${item.lower_bound != null ? item.lower_bound.toFixed(2) : '-'}</div>`,
                `<div>上限: ${item.upper_bound != null ? item.upper_bound.toFixed(2) : '-'}</div>`,
              ].join('')
            },
          },
        })

        // 上界轮廓线
        series.push({
          name: '上界',
          type: 'line',
          data: sorted.map(r => r.upper_bound ?? r.predicted_value),
          smooth: true,
          symbol: 'none',
          lineStyle: { color, width: 0 },
          z: 0,
        })

        // 下界轮廓线
        series.push({
          name: '下界',
          type: 'line',
          data: sorted.map(r => r.lower_bound ?? r.predicted_value),
          smooth: true,
          symbol: 'none',
          lineStyle: { color, width: 0 },
          z: 0,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}40` },
              { offset: 1, color: `${color}10` },
            ]),
          },
        })

        // 预测值主线（覆盖在面积上）
        series.push({
          name: label,
          type: 'line',
          data: values,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color, width: 2 },
          itemStyle: { color },
          z: 2,
          tooltip: {
            formatter: function (params) {
              const idx = params.dataIndex
              const item = sorted[idx]
              return [
                `<div style="font-size:12px;color:#999">${item.forecast_date}</div>`,
                `<div>${label}: <b>${item.predicted_value.toFixed(2)}</b></div>`,
                `<div>下限: ${item.lower_bound != null ? item.lower_bound.toFixed(2) : '-'}</div>`,
                `<div>上限: ${item.upper_bound != null ? item.upper_bound.toFixed(2) : '-'}</div>`,
              ].join('')
            },
          },
        })

        legendData.push(label)
      } else {
        series.push({
          name: label,
          type: chartMode.value === 'area' ? 'line' : 'line',
          data: values,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color, width: 2 },
          itemStyle: { color },
          areaStyle: chartMode.value === 'area' ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}40` },
              { offset: 1, color: `${color}10` },
            ]),
          } : undefined,
        })
        legendData.push(label)
      }
    } else {
      // 多组合：多条折线
      series.push({
        name: label,
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        areaStyle: chartMode.value === 'area' ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${color}30` },
            { offset: 1, color: `${color}05` },
          ]),
        } : undefined,
      })
      legendData.push(label)
    }
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#ddd',
      borderWidth: 1,
      textStyle: { color: '#333', fontSize: 13 },
    },
    legend: {
      data: legendData,
      bottom: 0,
      textStyle: { fontSize: 12 },
    },
    grid: {
      left: 50,
      right: 30,
      top: 20,
      bottom: 40,
    },
    xAxis: {
      type: 'category',
      data: keys.length === 1 ? groups[keys[0]].map(r => r.forecast_date) : [],
      axisLabel: {
        rotate: 45,
        fontSize: 11,
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '预测值',
      nameTextStyle: { fontSize: 12 },
      axisLabel: {
        fontSize: 11,
        formatter: (v) => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v.toFixed(0),
      },
      splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
    },
    dataZoom: keys.length > 20 ? [{
      type: 'inside',
      start: 0,
      end: 100,
    }, {
      type: 'slider',
      start: 0,
      end: 100,
      height: 24,
      bottom: 50,
    }] : undefined,
    series,
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(option, true)
  chartInstance.resize()
}

function destroyChart() {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

async function handleExport() {
  if (!filters.dataSourceId) {
    ElMessage.warning('请先选择数据源')
    return
  }
  exporting.value = true
  try {
    const params = {
      data_source_id: filters.dataSourceId,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
    }
    if (filters.modelId) params.model_id = filters.modelId
    if (filters.storeCode) params.store_code = filters.storeCode.trim()
    if (filters.matnr) params.matnr = filters.matnr.trim()
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }

    const blob = await exportForecastExcel(params)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `预测结果_${Date.now()}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败: ' + (e.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}

// 图表模式切换时重新渲染
watch(chartMode, () => {
  if (forecastData.value.length > 0) {
    nextTick(() => renderChart())
  }
})

onMounted(() => {
  loadDataSources()
  resizeHandler = () => {
    if (chartInstance) chartInstance.resize()
  }
  window.addEventListener('resize', resizeHandler)
})

onBeforeUnmount(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  destroyChart()
})
</script>

<style scoped>
.forecast-result-query {
  padding: 20px;
}

.chart-card {
  margin-top: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.forecast-chart {
  width: 100%;
  height: 400px;
}

.result-header {
  margin-bottom: 12px;
  font-size: 14px;
  color: #606266;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
