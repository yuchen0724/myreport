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
          <el-radio-group v-model="chartType" size="small" @change="handleChartTypeChange">
            <el-radio-button label="bar">柱状图</el-radio-button>
            <el-radio-button label="line">折线图</el-radio-button>
            <el-radio-button label="pie">饼图</el-radio-button>
          </el-radio-group>
          <ChartRenderer
            :chart-type="chartType"
            :data="chartData"
            :config="chartConfig"
          />
        </div>
        
        <!-- 数据表格 -->
        <el-table :data="queryResult.rows" style="width: 100%" max-height="400">
          <el-table-column
            v-for="(column, index) in queryResult.column"
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

// 根据查询结果自动推荐图表类型
const chartConfig = computed(() => {
  if (!queryResult.value || queryResult.value.column.length < 2) {
    return {}
  }
  return {
    title: queryResult.value.column[1] || '数据',
    x_axis: queryResult.value.column[0],
    y_axis: queryResult.value.column[1]
  }
})

// 自动分析数据并生成图表数据
const analyzeChartData = () => {
  if (!queryResult.value || !queryResult.value.rows || queryResult.value.rows.length === 0) {
    chartData.value = []
    return
  }

  const columns = queryResult.value.column || []
  const rows = queryResult.value.rows || []
  
  if (columns.length < 2) {
    chartData.value = []
    return
  }

  const xField = columns[0]
  const yField = columns[1]

  // 尝试将数据转换为图表格式
  const data = rows.slice(0, 20).map(row => ({
    x: String(row[0] ?? row[xField] ?? ''),
    y: Number(row[1] ?? row[yField] ?? 0)
  })).filter(item => !isNaN(item.y))

  // 如果第一列是数字，作为 X 轴
  const firstIsNumber = rows.slice(0, 5).every(row => !isNaN(Number(row[0])))

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
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.question) {
    ElMessage.warning('请输入自然语言问题')
    return
  }

  loading.value = true
  try {
    const response = await parseQuestion(form.value)
    suggestions.value = response.suggestions || []
    queryResult.value = response.query_result
    executionTimeMs.value = response.execution_time_ms
    
    // 分析数据生成图表
    analyzeChartData()
    
    // 根据数据特征自动选择图表类型
    autoSelectChartType()
    
    ElMessage.success('解析成功')
  } catch (error) {
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
}

// 根据数据特征自动选择图表类型
const autoSelectChartType = () => {
  if (!queryResult.value || queryResult.value.rows.length === 0) return
  
  const rowCount = queryResult.value.rows.length
  
  // 数据少于 5 条，用柱状图或饼图
  if (rowCount <= 5) {
    chartType.value = 'pie'
  } 
  // 数据较多，用折线图
  else if (rowCount > 10) {
    chartType.value = 'line'
  }
  else {
    chartType.value = 'bar'
  }
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

.chart-section .el-radio-group {
  margin-bottom: 10px;
}
</style>
