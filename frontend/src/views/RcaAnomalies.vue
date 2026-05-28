<template>
  <div class="rca-anomalies">
    <el-page-header @back="$router.push('/rca')" style="margin-bottom: 16px">
      <template #content>
        <span>异常根因分析</span>
      </template>
    </el-page-header>

    <!-- 任务信息 -->
    <el-card v-if="task" style="margin-bottom: 16px">
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="任务ID">{{ task.task_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="task.status === 'completed' ? 'success' : 'danger'" size="small">
            {{ task.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="分析日期">{{ task.analysis_date }}</el-descriptions-item>
        <el-descriptions-item label="周期">{{ task.period_days }}天</el-descriptions-item>
        <el-descriptions-item label="异常数">
          <el-tag v-if="task.anomaly_count" type="danger">{{ task.anomaly_count }}</el-tag>
          <span v-else>0</span>
        </el-descriptions-item>
        <el-descriptions-item label="总体变化">
          <span v-if="task.summary?.total_change_pct != null"
                :class="task.summary.total_change_pct < 0 ? 'text-danger' : 'text-success'">
            {{ task.summary.total_change_pct }}%
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 瀑布图 -->
    <el-card v-if="anomalies.length" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>异常贡献分析</span>
          <div style="display: flex; gap: 12px; align-items: center">
            <el-select v-model="chartDimFilter" size="small" style="width: 120px" @change="renderChart">
              <el-option label="全部维度" value="all" />
              <el-option label="品类" value="operation_category1_name" />
              <el-option label="门店" value="store_code" />
              <el-option label="商品" value="matnr" />
            </el-select>
            <el-radio-group v-model="chartType" size="small" @change="renderChart">
              <el-radio-button value="waterfall">瀑布图</el-radio-button>
              <el-radio-button value="compare">对比柱状图</el-radio-button>
              <el-radio-button value="rank">下降排名</el-radio-button>
              <el-radio-button value="treemap">树图</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      <div ref="chartRef" style="width: 100%; height: 400px"></div>
    </el-card>

    <!-- AI 解读 -->
    <el-card v-if="anomalies.length && !aiAnalysis" style="margin-bottom: 16px">
      <el-button
        type="primary"
        :loading="aiLoading"
        @click="handleAiAnalysis"
        icon="MagicStick"
      >
        {{ aiLoading ? 'AI 分析中...' : 'AI 智能解读' }}
      </el-button>
      <span style="margin-left: 12px; color: #909399; font-size: 13px">
        基于当前异常数据生成业务解读报告
      </span>
    </el-card>

    <!-- AI 解读结果 -->
    <el-card v-if="aiAnalysis" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>🤖 AI 业务解读</span>
          <el-button size="small" text @click="aiAnalysis = ''">关闭</el-button>
        </div>
      </template>
      <div class="ai-report" v-html="renderMarkdown(aiAnalysis)"></div>
    </el-card>

    <!-- 异常列表 - 按维度分组 -->
    <div v-if="selectedDim" style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
      <el-tag type="info" closable @close="clearFilter">
        已筛选：{{ selectedDim.dimVal }}
      </el-tag>
      <el-button size="small" text @click="clearFilter">清除筛选</el-button>
    </div>
    <el-card v-for="(group, dimType) in groupedAnomalies" :key="dimType" style="margin-bottom: 16px">
      <template #header>
        <span>{{ dimLabel[dimType] || dimType }}（{{ group.length }}）</span>
      </template>
      <el-table
        :data="group"
        v-loading="loading"
        style="width: 100%"
        row-key="id"
        @expand-change="handleExpand"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 12px 24px">
              <h4 style="margin: 0 0 8px">下钻详情</h4>
              <div v-if="row._drillLoading">加载中...</div>
              <div v-else-if="row._drillData && row._drillData.length">
                <el-table :data="row._drillData" size="small" border>
                  <el-table-column label="维度值" min-width="200">
                    <template #default="{ row: r }">
                      {{ r.dim_name ? r.dim_name + ' (' + r.dim_val + ')' : r.dim_val }}
                    </template>
                  </el-table-column>
                  <el-table-column label="当前值" width="120">
                    <template #default="{ row: r }">{{ formatVal(r.current_value ?? r.current_val) }}</template>
                  </el-table-column>
                  <el-table-column label="基线值" width="120">
                    <template #default="{ row: r }">{{ formatVal(r.baseline_value ?? r.baseline_val) }}</template>
                  </el-table-column>
                  <el-table-column label="变化" width="100">
                    <template #default="{ row: r }">
                      <span :class="r.change_pct < 0 ? 'text-danger' : 'text-success'">
                        {{ r.change_pct }}%
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="贡献度" width="100">
                    <template #default="{ row: r }">{{ r.contribution_pct }}%</template>
                  </el-table-column>
                </el-table>
              </div>
              <div v-else>无下钻数据</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="名称" min-width="200">
          <template #default="{ row }">
            {{ row.dimension_path.name || row.dimension_path[dimType] }}
          </template>
        </el-table-column>
        <el-table-column label="编码" width="120">
          <template #default="{ row }">
            {{ row.dimension_path[dimType] }}
          </template>
        </el-table-column>
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">{{ formatVal(row.current_value) }}</template>
        </el-table-column>
        <el-table-column label="基线值" width="120">
          <template #default="{ row }">{{ formatVal(row.baseline_value) }}</template>
        </el-table-column>
        <el-table-column label="变化" width="100">
          <template #default="{ row }">
            <span :class="row.change_pct < 0 ? 'text-danger' : 'text-success'">
              {{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="贡献度" width="100">
          <template #default="{ row }">{{ row.contribution_pct }}%</template>
        </el-table-column>
        <el-table-column label="严重度" width="100">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="!loading && anomalies.length === 0" description="未发现异常" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getRcaTask, getRcaAnomalies, rcaDrillDown, getRcaConfigs, rcaAiAnalysis } from '@/api/rca'
import * as echarts from 'echarts/core'
import { BarChart, TreemapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, TreemapChart, GridComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const taskId = route.params.taskId

const task = ref(null)
const anomalies = ref([])
const loading = ref(false)
const drillDimensions = ref([])  // 从配置获取的下钻维度列表
const aiLoading = ref(false)
const aiAnalysis = ref('')

const dimLabel = {
  operation_category1_name: '品类异常',
  store_code: '门店异常',
  matnr: '商品异常',
}

const groupedAnomalies = computed(() => {
  const groups = {}
  const list = selectedDim.value
    ? anomalies.value.filter(a => {
        const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
        return dim === selectedDim.value.dimType && a.dimension_path[dim] === selectedDim.value.dimVal
      })
    : anomalies.value
  for (const a of list) {
    const dim = Object.keys(a.dimension_path).find(k => k !== 'name') || 'unknown'
    if (!groups[dim]) groups[dim] = []
    groups[dim].push(a)
  }
  // 按维度层级排序：品类 → 门店 → 商品
  const order = ['operation_category1_name', 'store_code', 'matnr']
  const sorted = {}
  for (const k of order) {
    if (groups[k]) sorted[k] = groups[k]
  }
  for (const k of Object.keys(groups)) {
    if (!sorted[k]) sorted[k] = groups[k]
  }
  return sorted
})

const clearFilter = () => { selectedDim.value = null }

// AI 解读
const handleAiAnalysis = async () => {
  aiLoading.value = true
  aiAnalysis.value = ''
  try {
    const res = await rcaAiAnalysis(taskId)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') break
          if (data.startsWith('[ERROR]')) {
            ElMessage.error('AI 分析失败: ' + data.slice(8))
            break
          }
          aiAnalysis.value += data
        }
      }
    }
  } catch (e) {
    ElMessage.error('AI 分析请求失败: ' + (e.message || e))
  } finally {
    aiLoading.value = false
  }
}

const renderMarkdown = (html) => {
  // LLM 直接输出 HTML，前端只做安全清理
  if (!html) return ''
  return html
    // 移除 script 标签防止 XSS
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    // 移除 onclick 等事件属性
    .replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '')
}

const formatVal = (v) => {
  if (v == null) return '-'
  return (v / 10000).toFixed(2) + '万'
}

// 图表
const chartRef = ref(null)
const chartType = ref('waterfall')
const chartDimFilter = ref('all')
const selectedDim = ref(null)  // 点击图表选中的维度
let chartInstance = null

const getChartLabels = (a) => {
  const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
  const name = a.dimension_path.name || a.dimension_path[dim]
  return name.length > 10 ? name.slice(0, 10) + '…' : name
}

const getSorted = () => {
  let list = anomalies.value
  if (chartDimFilter.value !== 'all') {
    list = list.filter(a => {
      const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
      return dim === chartDimFilter.value
    })
  }
  return [...list]
    .sort((a, b) => Math.abs(b.change_pct || 0) - Math.abs(a.change_pct || 0))
    .slice(0, 10)
}

const tooltipFormatter = (sorted) => (params) => {
  const p = Array.isArray(params) ? params[0] : params
  const idx = p.dataIndex ?? p.treePathInfo?.[1]?.dataIndex
  if (idx == null || !sorted[idx]) return ''
  const a = sorted[idx]
  const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
  return `<b>${a.dimension_path.name || a.dimension_path[dim]}</b><br/>`
    + `变化: ${a.change_pct}%<br/>`
    + `贡献度: ${a.contribution_pct}%<br/>`
    + `当前: ${formatVal(a.current_value)}<br/>`
    + `基线: ${formatVal(a.baseline_value)}`
}

const renderChart = () => {
  if (!chartRef.value || !anomalies.value.length) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const sorted = getSorted()
  const names = sorted.map(getChartLabels)

  const optFn = { waterfall: optWaterfall, compare: optCompare, rank: optRank, treemap: optTreemap }
  chartInstance.setOption((optFn[chartType.value] || optWaterfall)(sorted, names))

  // 点击联动
  chartInstance.off('click')
  chartInstance.on('click', (params) => {
    const idx = params.dataIndex ?? params.treePathInfo?.[1]?.dataIndex
    if (idx == null || !sorted[idx]) return
    const a = sorted[idx]
    const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
    const dimVal = a.dimension_path[dim]
    // 再次点击同一项则取消过滤
    if (selectedDim.value?.dimType === dim && selectedDim.value?.dimVal === dimVal) {
      selectedDim.value = null
    } else {
      selectedDim.value = { dimType: dim, dimVal }
    }
  })
}

function optWaterfall(sorted, names) {
  let cum = 0
  const baseData = [], barData = []
  for (const a of sorted) {
    baseData.push(cum)
    barData.push(Math.abs(a.change_pct || 0))
    cum += Math.abs(a.change_pct || 0)
  }
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: tooltipFormatter(sorted) },
    grid: { left: 80, right: 30, top: 20, bottom: 80 },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', name: '累计下降 %', axisLabel: { formatter: '{value}%' } },
    series: [
      { name: '底座', type: 'bar', stack: 'w', itemStyle: { color: 'transparent' }, data: baseData, emphasis: { itemStyle: { color: 'transparent' } } },
      { name: '下降', type: 'bar', stack: 'w', itemStyle: { color: p => Math.abs(sorted[p.dataIndex]?.change_pct) >= 30 ? '#f56c6c' : '#e6a23c', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', formatter: p => `-${p.value.toFixed(1)}%`, fontSize: 11 }, data: barData },
    ],
  }
}

function optCompare(sorted, names) {
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: tooltipFormatter(sorted) },
    legend: { data: ['当前值', '基线值'], bottom: 0 },
    grid: { left: 80, right: 30, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', name: '万元', axisLabel: { formatter: v => (v / 10000).toFixed(0) } },
    series: [
      { name: '当前值', type: 'bar', barWidth: '30%', itemStyle: { color: '#409eff', borderRadius: [4, 4, 0, 0] },
        data: sorted.map(a => a.current_value || 0) },
      { name: '基线值', type: 'bar', barWidth: '30%', itemStyle: { color: '#909399', borderRadius: [4, 4, 0, 0] },
        data: sorted.map(a => a.baseline_value || 0) },
    ],
  }
}

function optRank(sorted, names) {
  const reversed = [...sorted].reverse()
  const rNames = reversed.map(getChartLabels)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: params => {
      const p = params[0]
      const a = reversed[p.dataIndex]
      const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
      return `<b>${a.dimension_path.name || a.dimension_path[dim]}</b><br/>变化: ${a.change_pct}%`
    }},
    grid: { left: 120, right: 40, top: 10, bottom: 20 },
    xAxis: { type: 'value', axisLabel: { formatter: v => `${v}%` } },
    yAxis: { type: 'category', data: rNames, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar', barWidth: '60%',
      itemStyle: { color: p => Math.abs(reversed[p.dataIndex]?.change_pct) >= 30 ? '#f56c6c' : '#e6a23c', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: p => `${reversed[p.dataIndex]?.change_pct}%`, fontSize: 11 },
      data: reversed.map(a => Math.abs(a.change_pct || 0)),
    }],
  }
}

function optTreemap(sorted) {
  return {
    tooltip: { formatter: params => {
      const a = sorted.find(s => getChartLabels(s) === params.name)
      if (!a) return ''
      const dim = Object.keys(a.dimension_path).find(k => k !== 'name')
      return `<b>${a.dimension_path.name || a.dimension_path[dim]}</b><br/>`
        + `变化: ${a.change_pct}%<br/>贡献度: ${a.contribution_pct}%`
    }},
    series: [{
      type: 'treemap', roam: false,
      breadcrumb: { show: false },
      label: { formatter: p => `${p.name}\n${p.value}%`, fontSize: 12 },
      data: sorted.map(a => ({
        name: getChartLabels(a),
        value: Math.abs(a.contribution_pct || 0.01),
        itemStyle: { color: Math.abs(a.change_pct) >= 30 ? '#f56c6c' : '#e6a23c' },
      })),
    }],
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const [taskRes, anomalyRes, cfgRes] = await Promise.all([
      getRcaTask(taskId), getRcaAnomalies(taskId), getRcaConfigs()
    ])
    task.value = taskRes.data || taskRes
    anomalies.value = (anomalyRes.data || anomalyRes).map(a => ({
      ...a,
      _drillData: null,
      _drillLoading: false,
    }))
    // 获取当前任务对应的配置的下钻维度
    const configs = cfgRes.data || cfgRes
    const cfg = configs.find(c => c.id === task.value?.metric_config_id)
    drillDimensions.value = cfg?.drill_dimensions || ['operation_category1_name', 'store_code', 'matnr']
    await nextTick()
    renderChart()
  } catch (e) {
    console.error('Load anomalies failed:', e)
  } finally {
    loading.value = false
  }
}

const handleExpand = async (row, expanded) => {
  if (expanded.length === 0 || row._drillData) return

  row._drillLoading = true
  try {
    const dim = Object.keys(row.dimension_path)[0]
    const dimVal = row.dimension_path[dim]
    // 下钻维度映射：支持正向和反向
    const nextDimMap = {
      operation_category1_name: 'store_code',
      store_code: 'matnr',
      matnr: 'store_code',  // 商品反向下钻到门店
    }
    const nextDim = nextDimMap[dim]
    if (!nextDim) {
      row._drillData = []
      return
    }
    const res = await rcaDrillDown({
      task_id: taskId,
      metric_name: row.metric_name,
      dimension: nextDim,
      filters: { [dim]: dimVal },
    })
    row._drillData = (res.data || res).rows || []
  } catch (e) {
    row._drillData = []
  } finally {
    row._drillLoading = false
  }
}

onMounted(async () => {
  await loadData()
  window.addEventListener('resize', () => chartInstance?.resize())
})

onUnmounted(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', () => chartInstance?.resize())
})
</script>

<style scoped>
.rca-anomalies {
  padding: 16px;
}
.text-danger {
  color: #f56c6c;
  font-weight: bold;
}
.text-success {
  color: #67c23a;
  font-weight: bold;
}
</style>
<style>
.ai-report {
  line-height: 1.8;
  color: #303133;
  max-width: 900px;
  font-size: 14px;
}
.ai-report h2 {
  margin: 20px 0 10px;
  font-size: 17px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 6px;
}
.ai-report h3 {
  margin: 16px 0 8px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.ai-report p {
  margin: 6px 0;
}
.ai-report ul, .ai-report ol {
  margin: 8px 0;
  padding-left: 24px;
}
.ai-report li {
  margin: 4px 0;
  line-height: 1.7;
}
.ai-report b {
  color: #303133;
  font-weight: 600;
}
.ai-report hr {
  border: none;
  border-top: 1px solid #ebeef5;
  margin: 20px 0;
}
</style>
