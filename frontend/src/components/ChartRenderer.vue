<!-- frontend/src/components/ChartRenderer.vue -->
<template>
  <div class="chart-renderer">
    <div ref="chartRef" style="width: 100%; height: 400px;"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import echarts from '@/utils/echarts'

const props = defineProps({
  chartType: {
    type: String,
    required: true
  },
  data: {
    type: Array,
    required: true
  },
  config: {
    type: Object,
    default: () => ({})
  }
})

const chartRef = ref(null)
let chartInstance = null

onMounted(() => {
  initChart()
})

watch(() => [props.chartType, props.data, props.config], () => {
  updateChart()
}, { deep: true })

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance) return

  const option = generateChartOption()
  chartInstance.setOption(option)
}

const generateChartOption = () => {
  const xData = props.data.map(item => item.x)
  const yData = props.data.map(item => item.y)

  const baseOption = {
    title: {
      text: props.config.title || '图表'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: xData
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: props.config.y_axis || '数值',
        type: props.chartType,
        data: yData,
        itemStyle: {
          color: props.config.color || '#409EFF'
        }
      }
    ]
  }

  // 针对不同图表类型的特殊配置
  if (props.chartType === 'pie') {
    baseOption.xAxis = null
    baseOption.yAxis = null
    baseOption.series[0].data = props.data.map(item => ({
      name: item.x,
      value: item.y
    }))
  }

  return baseOption
}
</script>

<style scoped>
.chart-renderer {
  width: 100%;
}
</style>
