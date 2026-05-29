<template>
  <div class="forecast-result-query">
    <el-card>
      <template #header>
        <span>预测结果查询</span>
      </template>

      <el-form :model="filters" label-width="90px">
        <el-row :gutter="16" style="width: 100%">
          <el-col :span="8">
            <el-form-item label="数据源" prop="dataSourceId">
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
            <el-form-item label="模型" prop="modelId">
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
                  :label="`模型 #${m.model_id} [${m.model_type}] (${formatDate(m.trained_at)})`"
                  :value="m.model_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="门店编码" prop="storeCode">
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
            <el-form-item label="商品编码" prop="matnr">
              <el-input
                v-model="filters.matnr"
                placeholder="输入商品编码"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预测日期" prop="dateRange">
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
            <el-form-item label="排序" prop="sortBy">
              <el-select v-model="filters.sortBy" style="width: 100%">
                <el-option label="预测日期" value="forecast_date" />
                <el-option label="预测值" value="predicted_value" />
                <el-option label="门店编码" value="store_code" />
                <el-option label="商品编码" value="matnr" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="方向" prop="sortOrder">
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
          <div class="chart-controls">
            <el-radio-group v-model="chartMode" size="small">
              <el-radio-button value="line">折线图</el-radio-button>
              <el-radio-button value="area">面积图</el-radio-button>
              <el-radio-button value="bar">柱状图</el-radio-button>
              <el-radio-button value="kline">K线图</el-radio-button>
              <el-radio-button value="heatmap">热力图</el-radio-button>
            </el-radio-group>
            <el-checkbox v-model="showStats" v-if="chartMode !== 'heatmap'" style="margin-left: 12px">
              显示统计线
            </el-checkbox>
          </div>
        </div>
      </template>
      <div ref="chartRef" class="forecast-chart" />
    </el-card>

    <!-- 统计摘要 -->
    <el-card v-if="hasData" style="margin-top: 16px" v-show="chartMode !== 'heatmap'">
      <template #header>
        <span>统计摘要</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">数据点</div>
            <div class="stat-value">{{ total }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">预测均值</div>
            <div class="stat-value">{{ stats.avg.toFixed(2) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">预测总和</div>
            <div class="stat-value">{{ formatNumber(stats.sum) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">置信区间覆盖率</div>
            <div class="stat-value">{{ stats.confidenceRate }}%</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card style="margin-top: 16px">
      <div class="result-header">
        <span v-if="total > 0">共 {{ total }} 条记录</span>
        <span v-else>&nbsp;</span>
      </div>

      <EnhancedTable
        :data="forecastData"
        :loading="loading"
        table-id="forecast-result"
        :show-toolbar="true"
        :summarizable="false"
        :enable-expand="true"
        :searchable="true"
        :max-height="500"
        :column-labels="{
          id: 'ID',
          store_code: '门店编码',
          matnr: '商品编码',
          ware_name: '商品名称',
          forecast_date: '预测日期',
          predicted_value: '预测值',
          lower_bound: '置信下限',
          upper_bound: '置信上限',
        }"
      >
        <template #cell-predicted_value="{ row }">
          {{ row.predicted_value.toFixed(2) }}
        </template>
        <template #cell-lower_bound="{ row }">
          {{ row.lower_bound != null ? row.lower_bound.toFixed(2) : '-' }}
        </template>
        <template #cell-upper_bound="{ row }">
          {{ row.upper_bound != null ? row.upper_bound.toFixed(2) : '-' }}
        </template>
      </EnhancedTable>

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
import echarts from '@/utils/echarts'
import EnhancedTable from '@/components/EnhancedTable.vue'
import { useFormPersistence } from '@/composables/useFormPersistence'

const { loadStored, saveToStorage } = useFormPersistence('forecast_result_filters', {
  dataSourceId: null,
  modelId: null,
  storeCode: '',
  matnr: '',
  dateRange: null,
  sortBy: 'forecast_date',
  sortOrder: 'asc',
})

const dataSources = ref([])
const models = ref([])
const loading = ref(false)
const exporting = ref(false)
const forecastData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = reactive(loadStored())

// 表单值变化时自动保存
watch(filters, () => saveToStorage(filters), { deep: true })

const hasData = computed(() => forecastData.value.length > 0)

// 图表相关
const chartRef = ref(null)
const chartMode = ref('line')
const showStats = ref(true)
const isChartMode = computed(() => forecastData.value.length > 0)

// 统计数据
const stats = computed(() => {
  const data = forecastData.value
  if (!data.length) return { avg: 0, sum: 0, max: 0, min: 0, confidenceRate: 0 }
  
  const values = data.map(r => r.predicted_value)
  const sum = values.reduce((a, b) => a + b, 0)
  const avg = sum / values.length
  const max = Math.max(...values)
  const min = Math.min(...values)
  
  // 置信区间覆盖率
  const withConfidence = data.filter(r => r.lower_bound != null && r.upper_bound != null)
  const rate = withConfidence.length > 0 ? Math.round((withConfidence.length / data.length) * 100) : 0
  
  return { avg, sum, max, min, confidenceRate: rate }
})

function formatNumber(num) {
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toFixed(0)
}
let chartInstance = null
let resizeHandler = null

function formatDate(iso) {
  if (!iso) return ''
  
  // 检测时区类型
  const isUTC = iso.endsWith('Z')
  const isCST = iso.includes('+08:00')
  
  if (isCST) {
    // 已经是 CST 时区，直接提取日期时间
    return iso.slice(0, 16).replace('T', ' ')
  } else if (isUTC) {
    // UTC 时间，转换为 CST (+8小时)
    const d = new Date(iso)
    const local = new Date(d.getTime() + 8 * 60 * 60 * 1000)
    const pad = n => String(n).padStart(2, '0')
    return `${local.getFullYear()}-${pad(local.getMonth()+1)}-${pad(local.getDate())} ${pad(local.getHours())}:${pad(local.getMinutes())}`
  }
  
  // naive datetime（无时区信息）：假设是 CST，直接提取
  // 格式如: 2026-05-19T07:07:09 或 2026-05-19 07:07:09
  if (iso.includes('T')) {
    return iso.slice(0, 16).replace('T', ' ')
  } else if (iso.includes(' ')) {
    return iso.slice(0, 16)
  }
  // 保守处理：原样返回
  return iso
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
    models.value = list.filter(m => m.status === 'ready' && Number(m.data_source_id) === Number(filters.dataSourceId))
    if (filters.modelId && !models.value.some(m => Number(m.model_id) === Number(filters.modelId))) {
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
    data_source_id: Number(filters.dataSourceId),
    page: page.value,
    page_size: pageSize.value,
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
  }
  if (filters.modelId) params.model_id = Number(filters.modelId)
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
  const defaults = {
    dataSourceId: null,
    modelId: null,
    storeCode: '',
    matnr: '',
    dateRange: null,
    sortBy: 'forecast_date',
    sortOrder: 'asc',
  }
  Object.assign(filters, defaults)
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
  // 确保 DOM 元素已布局（避免 ECharts 警告 Can't get DOM width or height）
  if (!chartRef.value.clientWidth || !chartRef.value.clientHeight) {
    setTimeout(() => renderChart(), 100)
    return
  }

  // 按 store_code@matnr 分组
  const groups = {}
  for (const row of data) {
    const key = getSeriesKey(row)
    if (!groups[key]) groups[key] = []
    groups[key].push(row)
  }

  const keys = Object.keys(groups)
  const isSingle = keys.length === 1
  const mode = chartMode.value

  // 颜色池
  const colorPalette = [
    '#5470c6', '#91cc75', '#fac858', '#ee6666',
    '#73c0de', '#3ba272', '#fc8452', '#9a60b4',
    '#ea7ccc', '#4a90d9',
  ]

  // 所有分组的公共日期轴（取并集排序）
  const allDates = [...new Set(data.map(r => r.forecast_date))].sort()

  // 预处理每个分组：排序后生成 date->value 映射
  const groupData = keys.map((key, idx) => {
    const items = groups[key]
    const color = colorPalette[idx % colorPalette.length]
    const sorted = [...items].sort(
      (a, b) => a.forecast_date.localeCompare(b.forecast_date)
    )
    const dateValueMap = {}
    for (const r of sorted) {
      dateValueMap[r.forecast_date] = r
    }
    const label = isSingle ? '预测值' : key
    return { key, color, sorted, dateValueMap, label, idx }
  })

  // ========== 热力图 ==========
  if (mode === 'heatmap') {
    const heatData = []
    const yLabels = keys
    for (let yi = 0; yi < groupData.length; yi++) {
      const { sorted } = groupData[yi]
      for (const r of sorted) {
        const xi = allDates.indexOf(r.forecast_date)
        if (xi >= 0) heatData.push([xi, yi, r.predicted_value])
      }
    }
    const allVals = heatData.map(d => d[2])
    const option = {
      tooltip: {
        position: 'top',
        formatter: (p) => {
          const r = groupData[p.data[1]].dateValueMap[allDates[p.data[0]]]
          return r
            ? `${r.forecast_date}<br/>${keys[p.data[1]]}<br/>预测值: <b>${r.predicted_value.toFixed(2)}</b>`
            : ''
        },
      },
      grid: { left: 120, right: 40, top: 10, bottom: 60 },
      xAxis: {
        type: 'category',
        data: allDates,
        axisLabel: { rotate: 45, fontSize: 10 },
        splitArea: { show: true },
      },
      yAxis: {
        type: 'category',
        data: yLabels,
        axisLabel: { fontSize: 11 },
        splitArea: { show: true },
      },
      visualMap: {
        min: allVals.length ? Math.min(...allVals) : 0,
        max: allVals.length ? Math.max(...allVals) : 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: { color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#fee090', '#fdae61', '#f46d43', '#d73027'] },
      },
      dataZoom: allDates.length > 30 ? [{ type: 'slider', start: 0, end: 100, bottom: 30, height: 20 }] : undefined,
      series: [{
        type: 'heatmap',
        data: heatData,
        label: { show: allDates.length <= 15 && keys.length <= 8, fontSize: 10, formatter: (p) => p.data[2].toFixed(1) },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      }],
    }
    if (!chartInstance) chartInstance = echarts.init(chartRef.value)
    chartInstance.setOption(option, true)
    chartInstance.resize()
    return
  }

  // ========== K线图 ==========
  if (mode === 'kline') {
    const series = []
    const legendData = []
    // K线需要 open/close/high/low，我们用预测值模拟：
    // open=前一天值, close=当天值, high=max(open,close)+波动, low=min(open,close)-波动
    groupData.forEach(({ key, color, sorted, label }) => {
      const klineData = []
      for (let i = 0; i < sorted.length; i++) {
        const val = sorted[i].predicted_value
        const prev = i > 0 ? sorted[i - 1].predicted_value : val
        const open = prev
        const close = val
        const spread = Math.abs(close - open) * 0.5 + Math.max(Math.abs(val) * 0.02, 0.5)
        const high = Math.max(open, close) + spread
        const low = Math.min(open, close) - spread
        klineData.push([open, close, low, high])
      }
      series.push({
        name: label,
        type: 'candlestick',
        data: klineData,
        itemStyle: { color: '#ef5350', color0: '#26a69a', borderColor: '#ef5350', borderColor0: '#26a69a' },
      })
      legendData.push(label)
    })
    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params) => {
          if (!Array.isArray(params)) return ''
          const p = params[0]
          const idx = p.dataIndex
          const d = allDates[idx] || ''
          let html = `<div style="font-size:12px;color:#999">${d}</div>`
          for (const s of params) {
            const [open, close, low, high] = s.data
            html += `<div>${s.seriesName}<br/>开:${open.toFixed(2)} 收:${close.toFixed(2)}<br/>低:${low.toFixed(2)} 高:${high.toFixed(2)}</div>`
          }
          return html
        },
      },
      legend: { data: legendData, bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 60, right: 30, top: 20, bottom: 50 },
      xAxis: {
        type: 'category',
        data: allDates,
        axisLabel: { rotate: 45, fontSize: 11 },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        name: '预测值',
        scale: true,
        axisLabel: { fontSize: 11, formatter: (v) => v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v.toFixed(0) },
        splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
      },
      dataZoom: allDates.length > 15 ? [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 24, bottom: 50 },
      ] : undefined,
      series,
    }
    if (!chartInstance) chartInstance = echarts.init(chartRef.value)
    chartInstance.setOption(option, true)
    chartInstance.resize()
    return
  }

  // ========== 折线 / 面积 / 柱状 ==========
  const series = []
  const legendData = []
  const markLines = []

  // 统计线数据
  if (showStats.value && data.length > 0) {
    const vals = data.map(r => r.predicted_value)
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length
    const sortedVals = [...vals].sort((a, b) => a - b)
    const median = sortedVals.length % 2 === 0
      ? (sortedVals[sortedVals.length / 2 - 1] + sortedVals[sortedVals.length / 2]) / 2
      : sortedVals[Math.floor(sortedVals.length / 2)]
    markLines.push(
      { name: '均值', yAxis: avg, lineStyle: { color: '#ee6666', type: 'dashed', width: 1.5 }, label: { formatter: `均值: ${avg.toFixed(2)}`, position: 'insideEndTop' } },
      { name: '中位数', yAxis: median, lineStyle: { color: '#fac858', type: 'dashed', width: 1.5 }, label: { formatter: `中位: ${median.toFixed(2)}`, position: 'insideEndTop' } },
    )
  }

  groupData.forEach(({ key, color, sorted, label }) => {
    const dates = sorted.map(r => r.forecast_date)
    const values = sorted.map(r => r.predicted_value)

    if (mode === 'bar') {
      series.push({
        name: label,
        type: 'bar',
        data: values,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color },
            { offset: 1, color: `${color}80` },
          ]),
          borderRadius: [2, 2, 0, 0],
        },
        barMaxWidth: 40,
        markLine: isSingle && markLines.length ? { data: markLines, symbol: 'none' } : undefined,
      })
      legendData.push(label)
    } else {
      // line or area
      const isArea = mode === 'area'
      const hasConfidence = isSingle && sorted.some(r => r.lower_bound != null)

      if (hasConfidence) {
        // 置信区间面积
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
        })
        // 上界
        series.push({
          name: '上界',
          type: 'line',
          data: sorted.map(r => r.upper_bound ?? r.predicted_value),
          smooth: true, symbol: 'none',
          lineStyle: { color, width: 0 }, z: 0,
        })
        // 下界
        series.push({
          name: '下界',
          type: 'line',
          data: sorted.map(r => r.lower_bound ?? r.predicted_value),
          smooth: true, symbol: 'none',
          lineStyle: { color, width: 0 }, z: 0,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}40` },
              { offset: 1, color: `${color}10` },
            ]),
          },
        })
      }

      // 主线
      series.push({
        name: label,
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'circle',
        symbolSize: isSingle ? 6 : 4,
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        areaStyle: isArea ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${color}40` },
            { offset: 1, color: `${color}10` },
          ]),
        } : undefined,
        z: 2,
        markLine: isSingle && markLines.length && !hasConfidence ? { data: markLines, symbol: 'none' } : undefined,
      })
      legendData.push(label)
    }
  })

  // 多分组时统计线放在第一个 series
  if (markLines.length && !isSingle && series.length > 0) {
    series[0].markLine = { data: markLines, symbol: 'none' }
  }

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
      left: 60,
      right: 30,
      top: 20,
      bottom: 50,
    },
    xAxis: {
      type: 'category',
      data: isSingle ? groupData[0].sorted.map(r => r.forecast_date) : allDates,
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
    dataZoom: allDates.length > 20 ? [{
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
      data_source_id: Number(filters.dataSourceId),
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
    }
    if (filters.modelId) params.model_id = Number(filters.modelId)
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

// 图表模式切换 / 统计线切换时重新渲染
watch([chartMode, showStats], () => {
  if (forecastData.value.length > 0) {
    nextTick(() => renderChart())
  }
})

onMounted(() => {
  loadDataSources()
  // 如果有持久化的数据源，自动加载对应的模型列表
  if (filters.dataSourceId) {
    loadModels()
  }
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

.stat-item {
  text-align: center;
  padding: 12px 0;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}
</style>
