<!-- frontend/src/views/ChartViewer.vue -->
<template>
  <div class="chart-viewer">
    <el-card class="config-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">📊 图表查看器</span>
          <el-tag type="success" size="small">炫酷模式</el-tag>
        </div>
      </template>

      <el-form :model="form" label-width="100px" class="config-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="数据源">
              <el-select 
                v-model="form.data_source_id" 
                placeholder="请选择数据源"
                style="width: 100%"
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
          
          <el-col :span="12">
            <el-form-item label="图表类型">
              <el-select 
                v-model="form.chart_config.chart_type" 
                placeholder="请选择图表类型"
                style="width: 100%"
              >
                <el-option label="📈 折线图" value="line" />
                <el-option label="📊 柱状图" value="bar" />
                <el-option label="🥧 饼图" value="pie" />
                <el-option label="🔵 散点图" value="scatter" />
                <el-option label="🎯 雷达图" value="radar" />
                <el-option label="🎚️ 仪表盘" value="gauge" />
                <el-option label="🔻 漏斗图" value="funnel" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="SQL 查询">
          <el-input
            v-model="form.sql"
            type="textarea"
            :rows="4"
            placeholder="请输入 SQL 查询语句"
            class="sql-input"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="X 轴字段">
              <el-input v-model="form.chart_config.x_axis" placeholder="X 轴字段名" />
            </el-form-item>
          </el-col>
          
          <el-col :span="8">
            <el-form-item label="Y 轴字段">
              <el-input v-model="form.chart_config.y_axis" placeholder="Y 轴字段名" />
            </el-form-item>
          </el-col>
          
          <el-col :span="8">
            <el-form-item label="图表标题">
              <el-input v-model="form.chart_config.title" placeholder="图表标题" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="配色主题">
              <el-select v-model="form.chart_config.colorTheme" style="width: 100%">
                <el-option label="💎 蓝色" value="blue" />
                <el-option label="🔮 紫色" value="purple" />
                <el-option label="💎 青色" value="cyan" />
                <el-option label="🔥 橙色" value="orange" />
                <el-option label="💚 绿色" value="green" />
                <el-option label="💖 粉色" value="pink" />
              </el-select>
            </el-form-item>
          </el-col>
          
          <el-col :span="8">
            <el-form-item label="图表高度">
              <el-input v-model="form.chart_config.height" placeholder="如: 400px" />
            </el-form-item>
          </el-col>
          
          <el-col :span="8">
            <el-form-item label=" ">
              <el-checkbox v-model="form.chart_config.showParticles">
                粒子特效
              </el-checkbox>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" @click="handleGenerate" :loading="loading" size="large">
            <el-icon class="el-icon--left"><MagicStick /></el-icon>
            生成图表
          </el-button>
          <el-button @click="handleClear" size="large">
            <el-icon class="el-icon--left"><Delete /></el-icon>
            清空
          </el-button>
          <el-button @click="handleRandomTheme" size="large" plain>
            <el-icon class="el-icon--left"><Refresh /></el-icon>
            随机主题
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 图表展示区域 -->
    <transition name="fade">
      <el-card v-if="chartData" class="chart-card" shadow="always">
        <ChartRenderer
          :chart-type="chartData.chart_type"
          :data="chartData.data"
          :config="chartData.config"
          :color-theme="chartData.config.colorTheme || 'blue'"
          :height="chartData.config.height || '400px'"
          :show-particles="chartData.config.showParticles"
          :dark-mode="true"
          :show-toolbox="true"
          @chart-click="handleChartClick"
          @chart-ready="handleChartReady"
        />
      </el-card>
    </transition>

    <!-- 示例数据提示 -->
    <el-card v-if="!chartData && !loading" class="tips-card" shadow="hover">
      <div class="tips-content">
        <el-icon class="tips-icon"><InfoFilled /></el-icon>
        <div class="tips-text">
          <h3>💡 快速开始</h3>
          <p>1. 选择数据源和图表类型</p>
          <p>2. 输入 SQL 查询语句</p>
          <p>3. 配置 X/Y 轴字段和图表标题</p>
          <p>4. 点击"生成图表"查看炫酷效果</p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Delete, Refresh, InfoFilled } from '@element-plus/icons-vue'
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
    colorTheme: 'blue',
    height: '400px',
    showParticles: false,
  }
})

const dataSources = ref([])
const chartData = ref(null)
const loading = ref(false)
let chartInstance = null

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
  chartData.value = null
  
  try {
    const response = await generateChart(form.value)
    chartData.value = {
      ...response,
      config: {
        ...response.config,
        colorTheme: form.value.chart_config.colorTheme,
        height: form.value.chart_config.height,
        showParticles: form.value.chart_config.showParticles,
      }
    }
    ElMessage.success('🎉 图表生成成功')
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

const handleRandomTheme = () => {
  const themes = ['blue', 'purple', 'cyan', 'orange', 'green', 'pink']
  const randomTheme = themes[Math.floor(Math.random() * themes.length)]
  form.value.chart_config.colorTheme = randomTheme
  ElMessage.success(`已切换到 ${randomTheme} 主题`)
}

const handleChartClick = (params) => {
  console.log('图表点击:', params)
  ElMessage.info(`点击了: ${params.name} - ${params.value}`)
}

const handleChartReady = (instance) => {
  chartInstance = instance
  console.log('图表已就绪')
}
</script>

<style scoped>
.chart-viewer {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.config-card {
  margin-bottom: 20px;
  border-radius: 12px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.config-form {
  padding: 10px 0;
}

.sql-input :deep(textarea) {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  background: linear-gradient(135deg, #f5f7fa 0%, #f0f0f3 100%);
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  transition: all 0.3s;
}

.sql-input :deep(textarea:focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.chart-card {
  border-radius: 12px;
  overflow: hidden;
  background: transparent;
}

.tips-card {
  border-radius: 12px;
  background: linear-gradient(135deg, #e8f4f8 0%, #f0f8ff 100%);
  border: 1px dashed #409eff;
}

.tips-content {
  display: flex;
  align-items: flex-start;
  padding: 10px;
}

.tips-icon {
  font-size: 48px;
  color: #409eff;
  margin-right: 20px;
  flex-shrink: 0;
}

.tips-text h3 {
  margin: 0 0 12px 0;
  color: #303133;
  font-size: 16px;
}

.tips-text p {
  margin: 6px 0;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

/* 过渡动画 */
.fade-enter-active {
  animation: fadeInUp 0.5s ease-out;
}

.fade-leave-active {
  animation: fadeInUp 0.3s ease-in reverse;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .chart-viewer {
    padding: 10px;
  }
  
  .config-form :deep(.el-col) {
    margin-bottom: 10px;
  }
}
</style>
