<!-- frontend/src/views/ChartViewer.vue -->
<template>
  <div class="chart-viewer">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>图表查看器</span>
        </div>
      </template>

      <el-form :model="form" label-width="120px">
        <el-form-item label="数据源">
          <el-select v-model="form.data_source_id" placeholder="请选择数据源">
            <el-option
              v-for="ds in dataSources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="SQL 查询">
          <el-input
            v-model="form.sql"
            type="textarea"
            :rows="3"
            placeholder="请输入 SQL 查询"
          />
        </el-form-item>

        <el-form-item label="图表类型">
          <el-select v-model="form.chart_config.chart_type" placeholder="请选择图表类型">
            <el-option label="折线图" value="line" />
            <el-option label="柱状图" value="bar" />
            <el-option label="饼图" value="pie" />
            <el-option label="散点图" value="scatter" />
          </el-select>
        </el-form-item>

        <el-form-item label="X 轴字段">
          <el-input v-model="form.chart_config.x_axis" placeholder="请输入 X 轴字段名" />
        </el-form-item>

        <el-form-item label="Y 轴字段">
          <el-input v-model="form.chart_config.y_axis" placeholder="请输入 Y 轴字段名" />
        </el-form-item>

        <el-form-item label="图表标题">
          <el-input v-model="form.chart_config.title" placeholder="请输入图表标题" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleGenerate" :loading="loading">
            生成图表
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </el-form-item>
      </el-form>

      <!-- 图表渲染 -->
      <div v-if="chartData" class="chart-container">
        <ChartRenderer
          :chart-type="chartData.chart_type"
          :data="chartData.data"
          :config="chartData.config"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { generateChart } from '@/api/chart'
import { getDataSourceList } from '@/api/data_source'
import ChartRenderer from '@/components/ChartRenderer.vue'

const form = ref({
  data_source_id: null,
  sql: '',
  chart_config: {
    chart_type: 'bar',
    x_axis: '',
    y_axis: '',
    title: '',
    color: '#409EFF'
  }
})

const dataSources = ref([])
const chartData = ref(null)
const loading = ref(false)

onMounted(async () => {
  await loadDataSources()
})

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSources.value = response
  } catch (error) {
    ElMessage.error('加载数据源失败')
  }
}

const handleGenerate = async () => {
  if (!form.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.sql) {
    ElMessage.warning('请输入 SQL 查询')
    return
  }
  if (!form.value.chart_config.x_axis || !form.value.chart_config.y_axis) {
    ElMessage.warning('请输入 X 轴和 Y 轴字段')
    return
  }

  loading.value = true
  try {
    const response = await generateChart(form.value)
    chartData.value = response
    ElMessage.success('图表生成成功')
  } catch (error) {
    ElMessage.error('图表生成失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleClear = () => {
  form.value.sql = ''
  form.value.chart_config.title = ''
  chartData.value = null
}
</script>

<style scoped>
.chart-viewer {
  padding: 20px;
}

.chart-container {
  margin-top: 20px;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
</style>
