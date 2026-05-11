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
          <el-table-column prop="sql" label="SQL" />
          <el-table-column prop="confidence" label="置信度" width="120">
            <template #default="{ row }">
              {{ (row.confidence * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="explanation" label="解释" />
        </el-table>
      </div>

      <!-- 查询结果：表格 + 图表 -->
      <div v-if="queryResult" class="query-result">
        <h4>查询结果</h4>
        
        <!-- 图表展示区域 -->
        <div v-if="chartData.length > 0" class="chart-section">
          <div class="chart-controls">
            <el-radio-group v-model="chartType" size="small" @change="handleChartTypeChange">
              <el-radio-button label="bar">📊 柱状图</el-radio-button>
              <el-radio-button label="line">📈 折线图</el-radio-button>
              <el-radio-button label="pie">🥧 饼图</el-radio-button>
              <el-radio-button label="scatter">🔵 散点图</el-radio-button>
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
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { parseQuestion } from '@/api/nl2sql'
import { getDataSourceList } from '@/api/data_source'
import ChartRenderer from '@/components/ChartRenderer.vue'

const form = ref({
  data_source_id: null,
  question: ''
})

const dataSource = ref([])
const suggestions = ref([])
const queryResult = ref(null)
const executionTimeMs = ref(null)
const loading = ref(false)

// 图表相关
const chartType = ref('bar')
const chartData = ref([])
const chartColorTheme = ref('blue')
const chartHeight = ref('350px')

// 根据查询结果自动推荐图表类型
const chartConfig = computed(() => {
  if (!queryResult.value || !queryResult.value.columns || queryResult.value.columns.length < 2) {
    return {}
  }
  return {
    title: queryResult.value.columns[1] || '数据',
    x_axis: queryResult.value.columns[0],
    y_axis: queryResult.value.columns[1]
  }
})

// 自动分析数据并生成图表数据
const analyzeChartData = () => {
  if (!queryResult.value || !queryResult.value.rows || queryResult.value.rows.length === 0) {
    console.log('[Chart] 无数据: queryResult 为空')
    chartData.value = []
    return
  }

  const columns = queryResult.value.columns || []
  const rows = queryResult.value.rows || []
  
  console.log('[Chart] 原始数据:', { columns, rows: rows.slice(0, 3) })
  
  if (columns.length < 2) {
    console.log('[Chart] 列数不足:', columns.length)
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
  
  console.log('[Chart] 列类型分析:', { numericIndices, stringIndices })
  
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
  console.log('[Chart] 智能选择字段:', { xField, yField, xFieldIndex, yFieldIndex })

  // 尝试将数据转换为图表格式，支持对象和数组两种格式
  const data = rows.slice(0, 20).map(row => {
    // 支持数组格式 row[0], row[1]
    let xVal, yVal
    
    if (Array.isArray(row)) {
      xVal = row[xFieldIndex]
      yVal = row[yFieldIndex]
      console.log('[Chart] 数组格式:', row, { xVal, yVal, xFieldIndex, yFieldIndex })
    } else if (typeof row === 'object') {
      // 支持对象格式
      xVal = row[xField] ?? row[xFieldIndex]
      yVal = row[yField] ?? row[yFieldIndex]
    } else {
      xVal = row
      yVal = row
    }
    
    return {
      x: String(xVal ?? ''),
      y: Number(yVal ?? 0)
    }
  }).filter(item => {
    const valid = !isNaN(item.y)
    if (!valid) console.log('[Chart] 过滤掉无效数据:', item)
    return valid
  })

  console.log('[Chart] 转换后数据:', data)
  chartData.value = data
}

onMounted(async () => {
  await loadDataSources()
})

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSource.value = response
  } catch (error) {
    ElMessage.error('加载数据源失败')
  }
}

const handleParse = async () => {
  if (!form.value.data_source_id) {
    console.log('[NL2SQL] ⚠️ 验证失败: 未选择数据源')
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.question) {
    console.log('[NL2SQL] ⚠️ 验证失败: 未输入问题')
    ElMessage.warning('请输入自然语言问题')
    return
  }

  const startTime = performance.now()
  console.group('[NL2SQL] 🔄 开始解析')
  console.log('├─ 数据源ID:', form.value.data_source_id)
  console.log('├─ 问题:', form.value.question)
  console.log('└─ 发起时间:', new Date().toISOString())
  console.groupEnd()

  loading.value = true
  try {
    console.log('[NL2SQL] ⏳ 请求中...')
    
    const response = await parseQuestion(form.value)
    const endTime = performance.now()
    
    suggestions.value = response.suggestions || []
    queryResult.value = response.query_result
    executionTimeMs.value = response.execution_time_ms

    console.group('[NL2SQL] ✅ 解析完成')
    console.log('├─ 客户端耗时:', `${(endTime - startTime).toFixed(2)}ms`)
    console.log('├─ 服务端执行时间:', `${response.execution_time_ms}ms`)
    console.log('├─ SQL建议数:', suggestions.value.length)
    console.log('├─ 选中SQL:', response.selected_sql?.substring(0, 100) + '...')
    console.log('├─ 查询结果:', queryResult.value ? {
      columns: queryResult.value.columns,
      rowCount: queryResult.value.rows?.length,
      total: queryResult.value.total
    } : 'null')
    console.groupEnd()

    // 分析数据生成图表
    console.log('[NL2SQL] 📊 开始分析图表数据...')
    analyzeChartData()

    // 根据数据特征自动选择图表类型
    autoSelectChartType()

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
    console.log('[NL2SQL] 🏁 请求结束, loading 状态:', loading.value)
  }
}

const handleClear = () => {
  form.value.question = ''
  suggestions.value = []
  queryResult.value = null
  executionTimeMs.value = null
  chartData.value = []
}

// 根据数据特征自动选择图表类型
const autoSelectChartType = () => {
  if (!queryResult.value || !queryResult.value.rows || queryResult.value.rows.length === 0) return

  const rowCount = queryResult.value.rows.length
  const columns = queryResult.value.columns || []
  
  console.log('[Chart] 自动选择图表类型:', { rowCount, columns })

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
  console.log('[Chart] 推荐图表类型:', recommendedType, reason)
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

.chart-section .el-radio-group {
  margin-bottom: 0;
}
</style>
