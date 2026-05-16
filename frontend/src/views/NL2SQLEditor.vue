<!-- frontend/src/views/NL2SQLEditor.vue -->
<template>
  <div class="nl2sql-editor">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>NL2SQL 查询</span>
        </div>
      </template>

      <el-form :model="form" label-width="120px">
        <el-form-item label="数据源">
          <el-select v-model="form.data_source_id" placeholder="请选择数据源">
            <el-option
              v-for="ds in dataSource"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="showGroupSelect" label="集团（选填）">
          <el-select v-model="form.group_id" placeholder="选择集团（自动从 dim_store 加载）" clearable filterable :loading="groupLoading" style="width: 320px">
            <el-option
              v-for="g in groupOptions"
              :key="g.group_id"
              :label="g.group_name"
              :value="g.group_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="自然语言问题">
          <el-input
            v-model="form.question"
            type="textarea"
            :rows="3"
            placeholder="请输入自然语言问题例如：查询用户表中的前10条记录"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleParse" :loading="loading">
            解析并执行
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </el-form-item>
      </el-form>

      <!-- SQL 建议 -->
      <div v-if="suggestions.length > 0" class="suggestions">
        <h4>SQL 建议</h4>
        <el-table :data="suggestions" style="width: 100%">
          <el-table-column label="SQL" min-width="350">
            <template #default="{ row }">
              <pre class="sql-code-block">{{ formatSQL(row.sql) }}</pre>
            </template>
          </el-table-column>
          <el-table-column prop="confidence" label="置信度" width="120">
            <template #default="{ row }">
              {{ (row.confidence * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column min-width="200">
            <template #header>
              <span>解释</span>
            </template>
            <template #default="{ row }">
              <span class="explanation-text">{{ row.explanation }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 查询结果：表格 + 图表 -->
      <div v-if="queryResult" class="query-result">
        <h4>查询结果</h4>
        
        <!-- 图表展示区域 -->
        <div v-if="chartData.length > 0" class="chart-section">
          <!-- 图表建议说明 -->
          <div v-if="recommendedChart && recommendedChart.reason" class="chart-recommend-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>图表建议：{{ recommendedChart.chart_type }} - {{ recommendedChart.reason }}</span>
          </div>
          
          <div class="chart-controls">
            <el-radio-group v-model="chartType" size="small" @change="handleChartTypeChange">
              <el-radio-button value="bar">📊 柱状图</el-radio-button>
              <el-radio-button value="line">📈 折线图</el-radio-button>
              <el-radio-button value="pie">🥧 饼图</el-radio-button>
              <el-radio-button value="scatter">🔵 散点图</el-radio-button>
            </el-radio-group>
            <el-select v-model="chartColorTheme" size="small" style="width: 120px; margin-left: 10px;">
              <el-option label="💎 蓝色" value="blue" />
              <el-option label="🔮 紫色" value="purple" />
              <el-option label="💎 青色" value="cyan" />
              <el-option label="🔥 橙色" value="orange" />
              <el-option label="💚 绿色" value="green" />
              <el-option label="💖 粉色" value="pink" />
            </el-select>
          </div>
          <!-- 字段映射选择 -->
          <div v-if="queryResult && queryResult.columns && queryResult.columns.length >= 1" class="field-mapping-section">
            <div class="field-mapping-header">
              <span>字段映射（选择图表 X/Y 轴对应的字段）</span>
            </div>
            <div class="field-mapping-controls">
              <el-form :inline="true" size="small" label-width="40px">
                <el-form-item label="X 轴">
                  <el-select
                    v-model="fieldMapping.xAxis"
                    @change="rebuildChartFromFields"
                    placeholder="选择X轴字段"
                    style="width: 180px"
                  >
                    <el-option
                      v-for="col in queryResult.columns"
                      :key="col"
                      :label="col"
                      :value="col"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="Y 轴">
                  <el-select
                    v-model="fieldMapping.yAxis"
                    @change="rebuildChartFromFields"
                    placeholder="选择Y轴字段"
                    style="width: 180px"
                  >
                    <el-option
                      v-for="col in queryResult.columns"
                      :key="col"
                      :label="col"
                      :value="col"
                    />
                  </el-select>
                </el-form-item>
              </el-form>
            </div>
          </div>
          <ChartRenderer
            :chart-type="chartType"
            :data="chartData"
            :config="chartConfig"
            :color-theme="chartColorTheme"
            :height="chartHeight"
            :dark-mode="false"
            :show-toolbox="true"
          />
        </div>
        
        <!-- 数据表格 -->
        <el-table :data="queryResult.rows" style="width: 100%" max-height="400">
          <el-table-column
            v-for="(column, index) in queryResult.columns"
            :key="index"
            :prop="index.toString()"
            :label="column"
            show-overflow-tooltip
          />
        </el-table>
        <div class="result-info">
          <span>共 {{ queryResult.total }} 条记录</span>
          <span>执行时间：{{ executionTimeMs }}ms</span>
        </div>
      </div>
    </el-card>
  </div></template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { parseQuestion, getGroups } from '@/api/nl2sql'
import { getDataSourceList } from '@/api/data_source'
import ChartRenderer from '@/components/ChartRenderer.vue'
import { formatSQL } from '@/utils/sqlFormat'

const form = ref({
  data_source_id: null,
  question: '',
  group_id: null
})

const dataSource = ref([])
const dsLoadGroupMap = ref({})  // {dsId: true/false} — 记录每个数据源是否开启集团加载
const showGroupSelect = computed(() => {
  return dsLoadGroupMap.value[form.value.data_source_id] === true
})
const groupOptions = ref([])
const groupLoading = ref(false)
const suggestions = ref([])
const queryResult = ref(null)
const executionTimeMs = ref(null)
const loading = ref(false)
const recommendedChart = ref(null)  // LLM 推荐的图表配置

// 图表相关
const chartType = ref('bar')
const chartData = ref([])
const chartColorTheme = ref('blue')
const chartHeight = ref('350px')

// 字段映射（用户可手动选择 X/Y 轴对应的列）
const fieldMapping = ref({ xAxis: '', yAxis: '' })

// 根据字段映射生成图表配置
const chartConfig = computed(() => {
  if (!queryResult.value || !queryResult.value.columns || queryResult.value.columns.length < 1) {
    return {}
  }
  const xField = fieldMapping.value.xAxis || queryResult.value.columns[0]
  const yField = fieldMapping.value.yAxis || (queryResult.value.columns.length > 1 ? queryResult.value.columns[1] : queryResult.value.columns[0])
  return {
    title: yField || '数据',
    x_axis: xField,
    y_axis: yField
  }
})

// 自动分析数据并生成图表数据
const analyzeChartData = () => {
  
  if (!queryResult.value || !queryResult.value.rows || queryResult.value.rows.length === 0) {
    chartData.value = []
    return
  }

  const columns = queryResult.value.columns || []
  const rows = queryResult.value.rows || []
  
  
  if (columns.length < 2) {
    chartData.value = []
    return
  }

  // 🎯 智能识别：找到数值列作为 Y 轴，类别列作为 X 轴
  let xFieldIndex = 0
  let yFieldIndex = 1
  
  // 检查每列的数据类型，找出数值列
  const numericIndices = []
  const stringIndices = []
  
  columns.forEach((col, idx) => {
    // 检查前几行该列的数据
    const sampleValues = rows.slice(0, 5).map(row => row[idx])
    const numericCount = sampleValues.filter(v => !isNaN(Number(v)) && v !== null && v !== '').length
    const stringCount = sampleValues.filter(v => v !== null && v !== '').length
    
    if (numericCount >= stringCount * 0.8 && numericCount > 0) {
      numericIndices.push(idx)
    } else if (stringCount > 0) {
      stringIndices.push(idx)
    }
  })
  
  
  // Y 轴优先用数值列，X 轴用类别列
  if (numericIndices.length > 0) {
    yFieldIndex = numericIndices[0] // 用第一个数值列作为 Y 轴
    // 找一个不是 Y 轴的类别列作为 X 轴
    xFieldIndex = stringIndices.length > 0 ? stringIndices[0] : (numericIndices.length > 1 ? numericIndices[1] : 0)
  } else {
    // 没有数值列，用第二列作为 Y 轴
    yFieldIndex = 1
  }
  
  const xField = columns[xFieldIndex]
  const yField = columns[yFieldIndex]

  // 设置字段映射默认值
  fieldMapping.value.xAxis = xField
  fieldMapping.value.yAxis = yField

  // 尝试将数据转换为图表格式，支持对象和数组两种格式
  const data = rows.slice(0, 20).map(row => {
    // 支持数组格式 row[0], row[1]
    let xVal, yVal
    
    if (Array.isArray(row)) {
      xVal = row[xFieldIndex]
      yVal = row[yFieldIndex]
    } else if (typeof row === 'object') {
      // 支持对象格式
      xVal = row[xField] ?? row[xFieldIndex]
      yVal = row[yField] ?? row[yFieldIndex]
    } else {
      xVal = row
      yVal = row
    }
    
    // Y轴值转换：优先转为数字，若失败则给默认值1（用于展示类别存在性）
    const yNum = Number(yVal ?? 0)
    return {
      x: String(xVal ?? ''),
      y: isNaN(yNum) ? 1 : yNum  // 字符类型Y轴默认为1
    }
  })

  chartData.value = data
}

/**
 * 根据 LLM 推荐的图表配置构建图表数据
 */
const buildChartFromLLMRecommendation = (config) => {
  if (!queryResult.value || !config) {
    analyzeChartData()
    autoSelectChartType()
    return
  }

  const columns = queryResult.value.columns || []
  const rows = queryResult.value.rows || []
  

  const xField = config.x_axis
  const yField = config.y_axis
  
  // 查找字段索引
  let xFieldIndex = columns.findIndex(c => c === xField || c.toLowerCase() === xField?.toLowerCase())
  let yFieldIndex = columns.findIndex(c => c === yField || c.toLowerCase() === yField?.toLowerCase())

  // 如果找不到精确匹配，尝试模糊匹配
  if (xFieldIndex === -1) {
    xFieldIndex = columns.findIndex(c => xField && c.toLowerCase().includes(xField.toLowerCase()))
  }
  if (yFieldIndex === -1) {
    yFieldIndex = columns.findIndex(c => yField && c.toLowerCase().includes(yField.toLowerCase()))
  }


  // 设置字段映射默认值
  if (xFieldIndex !== -1) {
    fieldMapping.value.xAxis = columns[xFieldIndex]
  }
  if (yFieldIndex !== -1) {
    fieldMapping.value.yAxis = columns[yFieldIndex]
  }

  // 如果找不到对应字段，回退到智能分析
  if (xFieldIndex === -1 || yFieldIndex === -1) {
    analyzeChartData()
    autoSelectChartType()
    return
  }

  // 根据 LLM 推荐的字段构建图表数据
  const data = rows.slice(0, 20).map(row => {
    let xVal, yVal
    
    if (Array.isArray(row)) {
      xVal = row[xFieldIndex]
      yVal = row[yFieldIndex]
    } else if (typeof row === 'object') {
      xVal = row[columns[xFieldIndex]]
      yVal = row[columns[yFieldIndex]]
    }
    
    return {
      x: String(xVal ?? ''),
      y: isNaN(Number(yVal ?? 0)) ? 1 : Number(yVal ?? 0)
    }
  })

  chartData.value = data
}

/**
 * 根据用户选择的字段映射重建图表数据
 */
const rebuildChartFromFields = () => {
  if (!queryResult.value || !queryResult.value.columns || !queryResult.value.rows) {
    return
  }

  const columns = queryResult.value.columns
  const rows = queryResult.value.rows
  const xField = fieldMapping.value.xAxis
  const yField = fieldMapping.value.yAxis

  if (!xField || !yField) return

  const xIndex = columns.indexOf(xField)
  const yIndex = columns.indexOf(yField)

  if (xIndex === -1 || yIndex === -1) return


  chartData.value = rows.slice(0, 20).map(row => {
    const xVal = Array.isArray(row) ? row[xIndex] : row[columns[xIndex]]
    const yVal = Array.isArray(row) ? row[yIndex] : row[columns[yIndex]]
    return {
      x: String(xVal ?? ''),
      y: isNaN(Number(yVal ?? 0)) ? 1 : Number(yVal ?? 0)
    }
  })
}

onMounted(async () => {
  await loadDataSources()
})

watch(() => form.value.data_source_id, () => {
  const dsId = form.value.data_source_id
  if (!dsId) {
    groupOptions.value = []
    form.value.group_id = null
    return
  }
  // 只有开启集团加载的数据源才调用加载接口
  if (dsLoadGroupMap.value[dsId]) {
    loadGroups()
  } else {
    groupOptions.value = []
    form.value.group_id = null
  }
})

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSource.value = response
    // 记录每个数据源的 load_group 属性
    const map = {}
    response.forEach(ds => { map[ds.id] = ds.load_group })
    dsLoadGroupMap.value = map
  } catch (error) {
    console.error('[NL2SQL] ❌ 数据源加载失败:', error)
    ElMessage.error('加载数据源失败')
  }
}

const loadGroups = async () => {
  const dsId = form.value.data_source_id
  if (!dsId) {
    groupOptions.value = []
    form.value.group_id = null
    return
  }
  groupLoading.value = true
  try {
    const groups = await getGroups(dsId)
    groupOptions.value = groups
    // 如果当前 group_id 不在新列表中，清空
    if (form.value.group_id && !groups.find(g => g.group_id === form.value.group_id)) {
      form.value.group_id = null
    }
  } catch (error) {
    console.error('[NL2SQL] ❌ 集团列表加载失败:', error)
    groupOptions.value = []
    // 加载失败时不清空当前选择，允许用户手动输入
  } finally {
    groupLoading.value = false
  }
}

const handleParse = async () => {
  if (!form.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.question) {
    ElMessage.warning('请输入自然语言问题')
    return
  }

  const startTime = performance.now()

  loading.value = true
  try {
    
    const response = await parseQuestion(form.value)
    const endTime = performance.now()
    
    suggestions.value = response.suggestions || []
    queryResult.value = response.query_result
    executionTimeMs.value = response.execution_time_ms
    recommendedChart.value = response.recommended_chart  // 保存 LLM 推荐的图表配置

    // 优先使用 LLM 推荐的图表配置，否则使用智能分析
    if (recommendedChart.value && recommendedChart.value.chart_type) {
      chartType.value = recommendedChart.value.chart_type
      // 根据 LLM 推荐的字段构建图表数据
      buildChartFromLLMRecommendation(recommendedChart.value)
    } else {
      // 分析数据生成图表
      analyzeChartData()
      // 根据数据特征自动选择图表类型
      autoSelectChartType()
    }

    ElMessage.success('解析成功')
  } catch (error) {
    console.error('[NL2SQL] ❌ 解析失败:', {
      error: error,
      message: error.message,
      stack: error.stack,
      response: error.response?.data
    })
    ElMessage.error('解析失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleClear = () => {
  form.value.question = ''
  suggestions.value = []
  queryResult.value = null
  executionTimeMs.value = null
  chartData.value = []
  chartType.value = 'bar'
  fieldMapping.value = { xAxis: '', yAxis: '' }

}

// 根据数据特征自动选择图表类型
const autoSelectChartType = () => {
  
  if (!queryResult.value || !queryResult.value.rows || queryResult.value.rows.length === 0) {
    return
  }

  const rowCount = queryResult.value.rows.length
  const columns = queryResult.value.columns || []
  
  
  // 获取 Y 轴数据的特征
  const yData = chartData.value.map(item => item.y)
  
  // 检查数据特征
  const total = yData.reduce((sum, v) => sum + v, 0)
  const maxVal = Math.max(...yData)
  const minVal = Math.min(...yData)
  const avgVal = total / yData.length
  
  // 检查是否有负值（不适合饼图）
  const hasNegative = yData.some(v => v < 0)
  
  // 检查数据是否有序（可能是时间序列）
  const isTimeSeries = isSorted(yData)
  
  // 检查数据是否差距悬殊（适合用对数刻度或饼图突出占比）
  const maxMinRatio = maxVal / (minVal || 1)
  const hasLargeGap = maxMinRatio > 100
  
  // 🎯 智能选择图表类型
  let recommendedType = 'bar'
  let reason = ''
  
  if (hasNegative) {
    // 有负值，用折线图或柱状图
    if (rowCount > 10) {
      recommendedType = 'line'
      reason = '数据有负值且数据量大，适合折线图'
    } else {
      recommendedType = 'bar'
      reason = '数据有负值，适合柱状图'
    }
  } else if (rowCount <= 5) {
    // 数据少，用饼图展示占比
    recommendedType = 'pie'
    reason = '数据量少(≤5条)，适合饼图展示占比'
  } else if (isTimeSeries && rowCount > 8) {
    // 时间序列数据，用折线图
    recommendedType = 'line'
    reason = '检测到时间序列趋势，适合折线图'
  } else if (hasLargeGap && rowCount <= 10) {
    // 数据差距大但数量不多，用饼图展示最大项占比
    recommendedType = 'pie'
    reason = '数据差距悬殊，适合饼图突出主要占比'
  } else if (rowCount > 10) {
    // 数据量大，用折线图展示趋势
    recommendedType = 'line'
    reason = '数据量大(>10条)，适合折线图展示趋势'
  } else if (rowCount >= 6 && rowCount <= 10) {
    // 中等数据量，用柱状图
    recommendedType = 'bar'
    reason = '中等数据量，适合柱状图对比'
  } else {
    // 默认用柱状图
    recommendedType = 'bar'
    reason = '默认使用柱状图'
  }

  chartType.value = recommendedType
}

// 检查数组是否有序（递增或递减）
const isSorted = (arr) => {
  if (arr.length < 3) return false
  let ascending = true
  let descending = true
  for (let i = 1; i < arr.length; i++) {
    if (arr[i] > arr[i - 1]) descending = false
    if (arr[i] < arr[i - 1]) ascending = false
  }
  return ascending || descending
}

const handleChartTypeChange = (type) => {
  chartType.value = type
}
</script>

<style scoped>
.nl2sql-editor {
  padding: 20px;
}

.suggestions,
.query-result {
  margin-top: 20px;
}

.suggestions h4,
.query-result h4 {
  margin-bottom: 10px;
}

.result-info {
  margin-top: 10px;
  color: #666;
}

.result-info span {
  margin-right: 20px;
}

.chart-section {
  margin-bottom: 20px;
}

.chart-controls {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  flex-wrap: wrap;
  gap: 10px;
}

.chart-recommend-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background-color: #f0f9ff;
  border: 1px solid #bae7ff;
  border-radius: 4px;
  color: #1890ff;
  font-size: 14px;
}

.chart-section .el-radio-group {
  margin-bottom: 0;
}

.field-mapping-section {
  margin-bottom: 16px;
  padding: 12px 16px;
  background-color: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
}

.field-mapping-header {
  margin-bottom: 10px;
  font-size: 13px;
  color: #666;
}

.field-mapping-header span::before {
  content: '⚙ ';
}

.field-mapping-controls .el-form-item {
  margin-bottom: 0;
}

/* SQL 格式化代码块样式 */
.sql-code-block {
  margin: 0;
  padding: 8px 12px;
  background-color: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  color: #24292e;
}

.explanation-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  display: block;
  max-height: 120px;
  overflow-y: auto;
}
</style>
