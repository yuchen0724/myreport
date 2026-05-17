<!-- frontend/src/components/ChartRenderer.vue -->
<template>
  <div class="chart-renderer" :class="{ 'light-mode': !darkMode }">
    <!-- 粒子背景 -->
    <div v-if="showParticles" class="particles-container" ref="particleRef"></div>
    
    <!-- 图表容器 -->
    <div ref="chartRef" class="chart-container"></div>
    
    <!-- 数据加载动画 -->
    <div v-if="loading" class="chart-loading">
      <div class="loading-spinner"></div>
      <p>数据加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue'
import echarts from '@/utils/echarts'
import {
  DARK_THEME,
  LIGHT_THEME,
  ANIMATION_CONFIG,
  TOOLBOX_CONFIG,
  createLinearGradient,
  createRadialGradient,
  createGlowEffect,
  createPieGradientColors,
  GRADIENT_COLORS,
} from '@/utils/chartTheme'

const props = defineProps({
  chartType: {
    type: String,
    required: true,
    validator: (val) => ['line', 'bar', 'pie', 'scatter', 'radar', 'gauge', 'funnel', 'heatmap', 'treemap', 'boxplot'].includes(val)
  },
  data: {
    type: Array,
    required: true
  },
  config: {
    type: Object,
    default: () => ({})
  },
  darkMode: {
    type: Boolean,
    default: true
  },
  showParticles: {
    type: Boolean,
    default: false
  },
  // 动画配置
  animationDuration: {
    type: Number,
    default: 1500
  },
  animationEasing: {
    type: String,
    default: 'cubicOut'
  },
  height: {
    type: String,
    default: '400px'
  },
  // 渐变色主题
  colorTheme: {
    type: String,
    default: 'blue',
    validator: (val) => Object.keys(GRADIENT_COLORS).includes(val)
  },
  // 是否显示工具箱
  showToolbox: {
    type: Boolean,
    default: true
  },
  // 是否启用动画
  enableAnimation: {
    type: Boolean,
    default: true
  },
  // 是否启用 DataZoom（按 chartType 条件生效）
  enableDataZoom: {
    type: Boolean,
    default: true
  },
  // 钻取配置：{ enabled: boolean, path: [{field, value, label}] }
  drillConfig: {
    type: Object,
    default: () => ({ enabled: false, path: [] })
  },
  // 联动组 ID：同一组 ID 的 ChartRenderer 在点击时联动
  linkageGroup: {
    type: String,
    default: ''
  },
})

const emit = defineEmits(['chartClick', 'chartReady', 'drillDown'])

const chartRef = ref(null)
const particleRef = ref(null)
const loading = ref(false)
let chartInstance = null
let particleAnimation = null
let isInitialized = false  // 标记是否已初始化

// 计算图表高度
const chartHeight = computed(() => props.height)

onMounted(() => {
  nextTick(() => {
    initChart()
    isInitialized = true
    if (props.showParticles) {
      initParticles()
    }
  })
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (particleAnimation) {
    cancelAnimationFrame(particleAnimation)
  }
  window.removeEventListener('resize', handleResize)
})

watch(
  () => [props.chartType, props.data, props.config, props.colorTheme],
  () => {
    // 使用 nextTick 确保 DOM 已渲染完成
    nextTick(() => {
      if (!chartInstance && chartRef.value) {
        console.log('[ChartRenderer] 初始化图表...')
        initChart()
        isInitialized = true
      } else if (chartInstance) {
        console.log('[ChartRenderer] 更新图表数据...', props.data)
        updateChart()
      } else {
        console.log('[ChartRenderer] 图表容器未就绪')
      }
    })
  },
  { deep: true }
)

// 初始化图表
const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value, props.darkMode ? 'dark' : null)
  
  // 根据主题应用不同的背景配置
  if (props.darkMode) {
    chartInstance.setOption(DARK_THEME)
  } else {
    // 浅色主题配置
    chartInstance.setOption(LIGHT_THEME)
  }
  
  updateChart()
  
  // 点击事件 — 同时支持钻取和联动
  chartInstance.on('click', (params) => {
    emit('chartClick', params)
    // 钻取：如果启用且点击的是分类轴数据
    if (props.drillConfig.enabled && params.name) {
      emit('drillDown', {
        field: props.config.x_axis || 'category',
        value: params.name,
        label: params.name,
      })
    }
    // 联动：触发同组其他图表
    if (props.linkageGroup) {
      window.__chartLinkage__ = window.__chartLinkage__ || {}
      window.__chartLinkage__[props.linkageGroup] = params
      window.dispatchEvent(new CustomEvent('chart-linkage', { detail: { group: props.linkageGroup, params } }))
    }
  })
  
  // 注册主题
  echarts.registerTheme('dark', DARK_THEME)
  echarts.registerTheme('light', LIGHT_THEME)
  
  window.addEventListener('resize', handleResize)
  
  // 联动监听
  if (props.linkageGroup) {
    const linkageHandler = (e) => {
      if (e.detail.group === props.linkageGroup) {
        const p = e.detail.params
        if (chartInstance && p.dataIndex != null && p.seriesIndex != null) {
          chartInstance.dispatchAction({ type: 'highlight', seriesIndex: p.seriesIndex, dataIndex: p.dataIndex })
        }
      }
    }
    window.addEventListener('chart-linkage', linkageHandler)
    // 在 unmount 时清理
    const origDispose = chartInstance.dispose.bind(chartInstance)
    chartInstance.dispose = () => {
      window.removeEventListener('chart-linkage', linkageHandler)
      origDispose()
    }
  }
  
  emit('chartReady', chartInstance)
}

// 更新图表
const updateChart = async () => {
  if (!chartInstance) return

  loading.value = true
  
  try {
    const option = generateChartOption()
    chartInstance.setOption(option, {
      notMerge: true,
      lazyUpdate: true,
    })
  } finally {
    loading.value = false
  }
}

// 生成图表配置
const generateChartOption = () => {
  const baseOption = {
    ...ANIMATION_CONFIG,
    // 支持通过 prop 覆盖动画时长
    animationDuration: props.animationDuration,
    animationEasing: props.animationEasing || ANIMATION_CONFIG.animationEasing,
    backgroundColor: 'transparent',
    title: {
      text: props.config.title || '',
      left: 'center',
      top: 10,
      textStyle: {
        color: props.darkMode ? '#ffffff' : '#333',
        fontSize: 18,
        fontWeight: 'bold',
        textShadowColor: props.darkMode ? 'rgba(0, 212, 255, 0.5)' : 'transparent',
        textShadowBlur: props.darkMode ? 10 : 0,
      },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: props.darkMode ? 'rgba(20, 25, 35, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      borderWidth: 1,
      textStyle: {
        color: props.darkMode ? '#ffffff' : '#333',
      },
      extraCssText: 'box-shadow: 0 4px 20px rgba(0, 212, 255, 0.3); border-radius: 8px;',
      confine: true,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 80,
      containLabel: true,
    },
  }

  // 添加工具箱
  if (props.showToolbox) {
    baseOption.toolbox = TOOLBOX_CONFIG
  }

  // 添加 DataZoom（折线图/散点图/柱状图/热力图启用）
  const zoomableCharts = ['line', 'bar', 'scatter', 'heatmap']
  if (props.enableDataZoom && zoomableCharts.includes(props.chartType)) {
    baseOption.dataZoom = [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: 10, height: 20 },
    ]
    // 为 dataZoom slider 留底部空间
    baseOption.grid = { ...baseOption.grid, bottom: props.chartType === 'heatmap' ? '10%' : '15%' }
  }

  // 根据图表类型生成配置
  switch (props.chartType) {
    case 'line':
      return generateLineOption(baseOption)
    case 'bar':
      return generateBarOption(baseOption)
    case 'pie':
      return generatePieOption(baseOption)
    case 'scatter':
      return generateScatterOption(baseOption)
    case 'radar':
      return generateRadarOption(baseOption)
    case 'gauge':
      return generateGaugeOption(baseOption)
    case 'funnel':
      return generateFunnelOption(baseOption)
    case 'heatmap':
      return generateHeatmapOption(baseOption)
    case 'treemap':
      return generateTreemapOption(baseOption)
    case 'boxplot':
      return generateBoxplotOption(baseOption)
    default:
      return baseOption
  }
}

// 📈 折线图配置
const generateLineOption = (baseOption) => {
  const xData = props.data.map(item => item.x)
  const yData = props.data.map(item => item.y)
  
  const gradient = createLinearGradient(echarts, props.colorTheme)
  const glow = createGlowEffect(props.colorTheme)

  return {
    ...baseOption,
    xAxis: {
      type: 'category',
      data: xData,
      name: props.config.x_axis_label || props.config.x_axis || '',
      nameTextStyle: {
        color: props.darkMode ? '#a0a0a0' : '#666',
        fontSize: 12,
      },
      axisLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.2)' : '#ddd',
        },
      },
      axisLabel: {
        color: props.darkMode ? '#a0a0a0' : '#666',
      },
    },
    yAxis: {
      type: 'value',
      name: props.config.y_axis_label || props.config.y_axis || '数值',
      nameTextStyle: {
        color: props.darkMode ? '#a0a0a0' : '#666',
        fontSize: 12,
      },
      splitLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.08)' : '#eee',
        },
      },
      axisLabel: {
        color: props.darkMode ? '#a0a0a0' : '#666',
      },
    },
    series: [
      {
        name: props.config.y_axis_label || props.config.y_axis || '数值',
        type: 'line',
        data: yData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        showSymbol: true,
        itemStyle: {
          color: gradient,
          ...glow,
        },
        lineStyle: {
          width: 3,
          color: gradient,
          ...glow,
        },
        areaStyle: {
          color: createLinearGradient(echarts, props.colorTheme, 'vertical'),
          opacity: 0.3,
        },
        emphasis: {
          focus: 'series',
          itemStyle: {
            ...glow,
            shadowBlur: 30,
          },
        },
      },
    ],
  }
}

// 📊 柱状图配置
const generateBarOption = (baseOption) => {
  const xData = props.data.map(item => item.x)
  const yData = props.data.map(item => item.y)
  
  const gradient = createLinearGradient(echarts, props.colorTheme, 'vertical')
  const glow = createGlowEffect(props.colorTheme)

  return {
    ...baseOption,
    xAxis: {
      type: 'category',
      data: xData,
      name: props.config.x_axis_label || props.config.x_axis || '',
      nameTextStyle: {
        color: props.darkMode ? '#a0a0a0' : '#666',
        fontSize: 12,
      },
      axisLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.2)' : '#ddd',
        },
      },
      axisLabel: {
        color: props.darkMode ? '#a0a0a0' : '#666',
        rotate: xData.length > 8 ? 30 : 0,
      },
    },
    yAxis: {
      type: 'value',
      name: props.config.y_axis_label || props.config.y_axis || '数值',
      nameTextStyle: {
        color: props.darkMode ? '#a0a0a0' : '#666',
        fontSize: 12,
      },
      splitLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.08)' : '#eee',
        },
      },
      axisLabel: {
        color: props.darkMode ? '#a0a0a0' : '#666',
      },
    },
    series: [
      {
        name: props.config.y_axis_label || props.config.y_axis || '数值',
        type: 'bar',
        data: yData,
        barMaxWidth: 60,
        itemStyle: {
          color: gradient,
          ...glow,
          borderRadius: [8, 8, 0, 0],
        },
        emphasis: {
          itemStyle: {
            ...glow,
            shadowBlur: 30,
          },
        },
        label: {
          show: yData.length <= 12,
          position: 'top',
          color: props.darkMode ? '#ffffff' : '#333',
          fontSize: 12,
          fontWeight: 'bold',
        },
      },
    ],
  }
}

// 🥧 饼图配置
const generatePieOption = (baseOption) => {
  const gradientColors = createPieGradientColors(echarts)
  
  const pieData = props.data.map((item, index) => ({
    name: item.x,
    value: item.y,
    itemStyle: {
      color: gradientColors[index % gradientColors.length],
      shadowBlur: 15,
      shadowColor: 'rgba(0, 0, 0, 0.3)',
    },
  }))

  return {
    ...baseOption,
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
      backgroundColor: props.darkMode ? 'rgba(20, 25, 35, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: {
        color: props.darkMode ? '#ffffff' : '#333',
      },
    },
    legend: {
      orient: 'vertical',
      right: 20,
      top: 'center',
      textStyle: {
        color: props.darkMode ? '#d0d0d0' : '#333',
      },
    },
    series: [
      {
        name: props.config.y_axis_label || props.config.y_axis || props.config.title || '占比',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 10,
          borderColor: props.darkMode ? '#1a1d29' : '#fff',
          borderWidth: 2,
        },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}: {d}%',
          color: props.darkMode ? '#d0d0d0' : '#333',
          fontSize: 12,
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 10,
          lineStyle: {
            color: props.darkMode ? 'rgba(255, 255, 255, 0.3)' : '#999',
          },
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
          itemStyle: {
            shadowBlur: 20,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 212, 255, 0.5)',
          },
        },
        data: pieData,
      },
    ],
  }
}

// 🔵 散点图配置
const generateScatterOption = (baseOption) => {
  const data = props.data.map(item => [item.x, item.y])
  const glow = createGlowEffect(props.colorTheme)

  return {
    ...baseOption,
    xAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.08)' : '#eee',
        },
      },
      axisLabel: {
        color: props.darkMode ? '#a0a0a0' : '#666',
      },
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.08)' : '#eee',
        },
      },
      axisLabel: {
        color: props.darkMode ? '#a0a0a0' : '#666',
      },
    },
    series: [
      {
        name: props.config.y_axis || '数据点',
        type: 'scatter',
        data: data,
        symbolSize: 12,
        itemStyle: {
          color: createRadialGradient(echarts, props.colorTheme),
          ...glow,
        },
        emphasis: {
          itemStyle: {
            ...glow,
            shadowBlur: 30,
          },
        },
      },
    ],
  }
}

// 🎯 雷达图配置
const generateRadarOption = (baseOption) => {
  const indicator = props.data.map(item => ({
    name: item.x,
    max: props.config.maxValue || Math.max(...props.data.map(d => d.y)) * 1.2,
  }))

  const gradient = createLinearGradient(echarts, props.colorTheme)

  return {
    ...baseOption,
    radar: {
      indicator: indicator,
      shape: 'polygon',
      splitNumber: 5,
      axisName: {
        color: props.darkMode ? '#a0a0a0' : '#666',
        fontSize: 12,
      },
      splitLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.1)' : '#ddd',
        },
      },
      splitArea: {
        areaStyle: {
          color: props.darkMode 
            ? ['rgba(0, 212, 255, 0.02)', 'rgba(0, 212, 255, 0.05)']
            : ['rgba(0, 0, 0, 0.02)', 'rgba(0, 0, 0, 0.05)'],
        },
      },
      axisLine: {
        lineStyle: {
          color: props.darkMode ? 'rgba(255, 255, 255, 0.2)' : '#ddd',
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: props.data.map(item => item.y),
            name: props.config.title || '数据',
            areaStyle: {
              color: gradient,
              opacity: 0.3,
            },
            lineStyle: {
              width: 2,
              color: gradient,
            },
            itemStyle: {
              color: gradient,
            },
          },
        ],
      },
    ],
  }
}

// 🎚️ 仪表盘配置
const generateGaugeOption = (baseOption) => {
  const value = props.data[0]?.y || 0
  const max = props.config.maxValue || 100
  const gradient = createLinearGradient(echarts, props.colorTheme, 'horizontal')

  return {
    ...baseOption,
    series: [
      {
        type: 'gauge',
        center: ['50%', '60%'],
        radius: '80%',
        min: 0,
        max: max,
        splitNumber: 10,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.3, '#ff5e3a'],
              [0.7, '#ffd700'],
              [1, '#00ff87'],
            ],
          },
        },
        pointer: {
          itemStyle: {
            color: gradient,
          },
        },
        axisTick: {
          distance: -20,
          length: 8,
          lineStyle: {
            color: props.darkMode ? 'rgba(255, 255, 255, 0.3)' : '#999',
            width: 2,
          },
        },
        splitLine: {
          distance: -20,
          length: 20,
          lineStyle: {
            color: props.darkMode ? 'rgba(255, 255, 255, 0.5)' : '#666',
            width: 3,
          },
        },
        axisLabel: {
          color: props.darkMode ? '#a0a0a0' : '#666',
          distance: 30,
          fontSize: 12,
        },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          color: props.darkMode ? '#ffffff' : '#333',
          fontSize: 24,
          fontWeight: 'bold',
          offsetCenter: [0, '70%'],
        },
        data: [
          {
            value: value,
            name: props.config.title || '数值',
          },
        ],
      },
    ],
  }
}

// 🔻 漏斗图配置
const generateFunnelOption = (baseOption) => {
  const gradientColors = createPieGradientColors(echarts)
  
  const funnelData = props.data.map((item, index) => ({
    name: item.x,
    value: item.y,
    itemStyle: {
      color: gradientColors[index % gradientColors.length],
    },
  }))

  return {
    ...baseOption,
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}',
      backgroundColor: props.darkMode ? 'rgba(20, 25, 35, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      textStyle: {
        color: props.darkMode ? '#ffffff' : '#333',
      },
    },
    series: [
      {
        name: props.config.title || '漏斗',
        type: 'funnel',
        left: '10%',
        top: 60,
        bottom: 60,
        width: '80%',
        min: 0,
        max: Math.max(...props.data.map(d => d.y)),
        minSize: '20%',
        maxSize: '100%',
        sort: 'descending',
        gap: 2,
        label: {
          show: true,
          position: 'inside',
          color: '#ffffff',
          fontWeight: 'bold',
        },
        labelLine: {
          length: 10,
          lineStyle: {
            width: 1,
            type: 'solid',
          },
        },
        itemStyle: {
          borderColor: props.darkMode ? '#1a1d29' : '#fff',
          borderWidth: 1,
        },
        emphasis: {
          label: {
            fontSize: 14,
          },
        },
        data: funnelData,
      },
    ],
  }
}

// 🗺️ 热力图配置
const generateHeatmapOption = (baseOption) => {
  // 热力图需要 [x, y, value] 三元组，数据格式和普通图表不同
  // 使用 config.heatmapData 作为三维数组
  const heatmapData = props.config.heatmapData || props.data.map(item => [item.x, item.y])
  const xCategories = [...new Set(heatmapData.map(d => d[0]))]
  const yCategories = [...new Set(heatmapData.map(d => d[1]))]

  return {
    ...baseOption,
    tooltip: {
      position: 'top',
      formatter: (p) => `X: ${p.data[0]}<br/>Y: ${p.data[1]}<br/>值: ${p.data[2] || '-'}`,
    },
    xAxis: {
      type: 'category',
      data: xCategories,
      splitArea: { show: true },
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: 'category',
      data: yCategories,
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max: Math.max(...heatmapData.map(d => d[2] || 1), 1),
      calculable: true,
      orient: 'vertical',
      right: 0,
      top: 'center',
      inRange: {
        color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#fee090', '#fdae61', '#f46d43', '#d73027'],
      },
    },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      label: { show: heatmapData.length <= 50 },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
      },
    }],
  }
}

// 📦 矩形树图配置
const generateTreemapOption = (baseOption) => {
  const treemapData = props.data.map(item => ({
    name: item.x,
    value: item.y,
  }))

  return {
    ...baseOption,
    tooltip: {
      formatter: (p) => `${p.name}: ${p.value}`,
    },
    series: [{
      type: 'treemap',
      data: treemapData,
      roam: true,
      width: '90%',
      height: '80%',
      top: 60,
      label: {
        show: true,
        formatter: (p) => `${p.name}\n${p.value}`,
        fontSize: 12,
      },
      itemStyle: {
        borderColor: props.darkMode ? '#1a1d29' : '#fff',
        borderWidth: 2,
        borderRadius: 4,
      },
      levels: [{
        colorSaturation: [0.3, 0.6],
        itemStyle: {
          borderColorSaturation: 0.7,
          gapWidth: 2,
        },
      }],
    }],
  }
}

// 📦 箱线图配置
const generateBoxplotOption = (baseOption) => {
  // 箱线图期望数据格式：[{ x: '类别1', y: [min, Q1, median, Q3, max] }, ...]
  const xData = props.data.map(item => item.x)
  const yData = props.data.map(item => Array.isArray(item.y) ? item.y : [0, 0, 0, 0, 0])

  return {
    ...baseOption,
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: { rotate: xData.length > 8 ? 30 : 0 },
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: { color: props.darkMode ? 'rgba(255,255,255,0.08)' : '#eee' },
      },
    },
    series: [{
      type: 'boxplot',
      data: yData,
      itemStyle: {
        color: createLinearGradient(echarts, props.colorTheme),
      },
      emphasis: {
        itemStyle: { shadowBlur: 20 },
      },
    }],
  }
}

// 🎨 粒子动画
const initParticles = () => {
  if (!particlesRef.value) return
  
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  particlesRef.value.appendChild(canvas)
  
  const particles = []
  const particleCount = 50
  
  // 设置画布尺寸
  const resizeCanvas = () => {
    canvas.width = particlesRef.value.offsetWidth
    canvas.height = particlesRef.value.offsetHeight
  }
  resizeCanvas()
  
  // 创建粒子
  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      radius: Math.random() * 2 + 1,
      opacity: Math.random() * 0.5 + 0.2,
    })
  }
  
  // 动画循环
  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    particles.forEach(p => {
      p.x += p.vx
      p.y += p.vy
      
      // 边界检测
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1
      
      // 绘制粒子
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(0, 212, 255, ${p.opacity})`
      ctx.fill()
    })
    
    // 绘制连线
    particles.forEach((p1, i) => {
      particles.slice(i + 1).forEach(p2 => {
        const dx = p1.x - p2.x
        const dy = p1.y - p2.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        
        if (dist < 100) {
          ctx.beginPath()
          ctx.moveTo(p1.x, p1.y)
          ctx.lineTo(p2.x, p2.y)
          ctx.strokeStyle = `rgba(0, 212, 255, ${0.1 * (1 - dist / 100)})`
          ctx.stroke()
        }
      })
    })
    
    particleAnimation = requestAnimationFrame(animate)
  }
  
  animate()
  window.addEventListener('resize', resizeCanvas)
}

// 窗口大小改变处理
const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

// 暴露方法
defineExpose({
  getChartInstance: () => chartInstance,
  resize: () => chartInstance?.resize(),
  setOption: (option) => chartInstance?.setOption(option),
})
</script>

<style scoped>
.chart-renderer {
  position: relative;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
}

/* 浅色模式 - 适配页面主背景 */
.chart-renderer.light-mode {
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fc 100%);
  box-shadow: 
    0 4px 16px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  border: 1px solid #e8ecf0;
}

/* 深色模式 - 可选 */
.chart-renderer.dark-mode {
  background: linear-gradient(135deg, rgba(26, 29, 41, 0.95) 0%, rgba(20, 23, 33, 0.98) 100%);
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.1);
}

.chart-container {
  width: 100%;
  height: v-bind(chartHeight);
  position: relative;
  z-index: 2;
}

.particles-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  pointer-events: none;
  opacity: 0.6;
}

.particles-container canvas {
  width: 100%;
  height: 100%;
}

/* 加载动画 */
.chart-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  z-index: 10;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto 10px;
  border: 3px solid rgba(0, 212, 255, 0.2);
  border-top-color: #00d4ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.chart-loading p {
  color: #a0a0a0;
  font-size: 14px;
  margin: 0;
}

/* 深色模式下的发光效果 */
.chart-renderer.dark-mode::before {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  background: linear-gradient(45deg, 
    rgba(0, 212, 255, 0.1),
    rgba(178, 75, 243, 0.1),
    rgba(0, 255, 200, 0.1),
    rgba(0, 212, 255, 0.1)
  );
  background-size: 400% 400%;
  border-radius: 10px;
  z-index: -1;
  animation: gradient-border 8s ease infinite;
  opacity: 0.5;
}

@keyframes gradient-border {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}
</style>
