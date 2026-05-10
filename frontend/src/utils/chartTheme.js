/**
 * 炫酷图表主题配置
 * 包含渐变色、发光效果、动画配置
 */

// 🎨 渐变色配置 - 科技感配色方案
export const GRADIENT_COLORS = {
  // 蓝色系渐变
  blue: {
    start: '#00d4ff',
    end: '#0066ff',
    glow: 'rgba(0, 212, 255, 0.5)',
  },
  // 紫色系渐变
  purple: {
    start: '#b24bf3',
    end: '#6b5bff',
    glow: 'rgba(178, 75, 243, 0.5)',
  },
  // 青色系渐变
  cyan: {
    start: '#00ffc8',
    end: '#00a8cc',
    glow: 'rgba(0, 255, 200, 0.5)',
  },
  // 橙色系渐变
  orange: {
    start: '#ff9500',
    end: '#ff5e3a',
    glow: 'rgba(255, 149, 0, 0.5)',
  },
  // 绿色系渐变
  green: {
    start: '#00ff87',
    end: '#00c853',
    glow: 'rgba(0, 255, 135, 0.5)',
  },
  // 粉色系渐变
  pink: {
    start: '#ff6b9d',
    end: '#c44569',
    glow: 'rgba(255, 107, 157, 0.5)',
  },
}

// 饼图/环形图配色方案
export const PIE_GRADIENT_COLORS = [
  ['#00d4ff', '#0066ff'],  // 蓝色
  ['#b24bf3', '#6b5bff'],  // 紫色
  ['#00ffc8', '#00a8cc'],  // 青色
  ['#ff9500', '#ff5e3a'],  // 橙色
  ['#00ff87', '#00c853'],  // 绿色
  ['#ff6b9d', '#c44569'],  // 粉色
  ['#ffd700', '#ff8c00'],  // 金色
  ['#00bfff', '#1e90ff'],  // 深蓝
  ['#ff69b4', '#ff1493'],  // 深粉
  ['#7b68ee', '#6a5acd'],  // 紫罗兰
]

// 🌟 深色主题配置
export const DARK_THEME = {
  // 背景色
  backgroundColor: 'transparent',
  
  // 标题样式
  title: {
    textStyle: {
      color: '#ffffff',
      fontSize: 18,
      fontWeight: 'bold',
      textShadowColor: 'rgba(0, 212, 255, 0.5)',
      textShadowBlur: 10,
    },
    subtextStyle: {
      color: '#a0a0a0',
      fontSize: 12,
    },
  },
  
  // 图例样式
  legend: {
    textStyle: {
      color: '#d0d0d0',
      fontSize: 12,
    },
    pageTextStyle: {
      color: '#d0d0d0',
    },
  },
  
  // 提示框样式
  tooltip: {
    backgroundColor: 'rgba(20, 25, 35, 0.95)',
    borderColor: 'rgba(0, 212, 255, 0.3)',
    borderWidth: 1,
    textStyle: {
      color: '#ffffff',
      fontSize: 13,
    },
    extraCssText: 'box-shadow: 0 4px 20px rgba(0, 212, 255, 0.3); border-radius: 8px;',
  },
  
  // 坐标轴样式
  categoryAxis: {
    axisLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.2)',
      },
    },
    axisTick: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.2)',
      },
    },
    axisLabel: {
      color: '#a0a0a0',
      fontSize: 11,
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.08)',
      },
    },
  },
  
  valueAxis: {
    axisLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.2)',
      },
    },
    axisTick: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.2)',
      },
    },
    axisLabel: {
      color: '#a0a0a0',
      fontSize: 11,
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.08)',
      },
    },
  },
}

// 🎬 动画配置
export const ANIMATION_CONFIG = {
  // 入场动画
  animationDuration: 1500,
  animationEasing: 'cubicOut',
  
  // 数据更新动画
  animationDurationUpdate: 800,
  animationEasingUpdate: 'cubicInOut',
  
  // 退出动画
  animationExit: true,
}

// ☀️ 浅色主题配置 - 适配页面主背景
export const LIGHT_THEME = {
  // 背景色透明，与页面融合
  backgroundColor: 'transparent',
  
  // 标题样式
  title: {
    textStyle: {
      color: '#303133',
      fontSize: 18,
      fontWeight: 'bold',
    },
    subtextStyle: {
      color: '#909399',
      fontSize: 12,
    },
  },
  
  // 图例样式
  legend: {
    textStyle: {
      color: '#606266',
      fontSize: 12,
    },
    pageTextStyle: {
      color: '#909399',
    },
  },
  
  // 提示框样式
  tooltip: {
    backgroundColor: 'rgba(255, 255, 255, 0.98)',
    borderColor: '#dcdfe6',
    borderWidth: 1,
    textStyle: {
      color: '#303133',
      fontSize: 13,
    },
    extraCssText: 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1); border-radius: 8px;',
  },
  
  // 坐标轴样式
  categoryAxis: {
    axisLine: {
      lineStyle: {
        color: '#dcdfe6',
      },
    },
    axisTick: {
      lineStyle: {
        color: '#dcdfe6',
      },
    },
    axisLabel: {
      color: '#606266',
      fontSize: 11,
    },
    splitLine: {
      lineStyle: {
        color: '#f0f2f5',
      },
    },
  },
  
  valueAxis: {
    axisLine: {
      lineStyle: {
        color: '#dcdfe6',
      },
    },
    axisTick: {
      lineStyle: {
        color: '#dcdfe6',
      },
    },
    axisLabel: {
      color: '#606266',
      fontSize: 11,
    },
    splitLine: {
      lineStyle: {
        color: '#f0f2f5',
      },
    },
  },
}

// 🔥 创建渐变色对象
export function createLinearGradient(echarts, colorKey = 'blue', direction = 'vertical') {
  const color = GRADIENT_COLORS[colorKey] || GRADIENT_COLORS.blue
  
  let x = 0, y = 0, x2 = 0, y2 = 1
  if (direction === 'horizontal') {
    x = 0; y = 0; x2 = 1; y2 = 0
  } else if (direction === 'diagonal') {
    x = 0; y = 0; x2 = 1; y2 = 1
  }
  
  return new echarts.graphic.LinearGradient(x, y, x2, y2, [
    { offset: 0, color: color.start },
    { offset: 1, color: color.end },
  ])
}

// 🌈 创建径向渐变（用于散点图、饼图等）
export function createRadialGradient(echarts, colorKey = 'blue') {
  const color = GRADIENT_COLORS[colorKey] || GRADIENT_COLORS.blue
  
  return new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
    { offset: 0, color: color.start },
    { offset: 1, color: color.end },
  ])
}

// ✨ 创建发光效果
export function createGlowEffect(colorKey = 'blue') {
  const color = GRADIENT_COLORS[colorKey] || GRADIENT_COLORS.blue
  return {
    shadowBlur: 20,
    shadowColor: color.glow,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
  }
}

// 🎨 为饼图创建渐变色数组
export function createPieGradientColors(echarts) {
  return PIE_GRADIENT_COLORS.map(([start, end]) => 
    new echarts.graphic.LinearGradient(0, 0, 1, 1, [
      { offset: 0, color: start },
      { offset: 1, color: end },
    ])
  )
}

// 📊 通用工具箱配置
export const TOOLBOX_CONFIG = {
  show: true,
  right: 20,
  top: 10,
  feature: {
    saveAsImage: {
      title: '保存为图片',
      pixelRatio: 2,
      backgroundColor: '#1a1d29',
    },
    dataView: {
      title: '数据视图',
      lang: ['数据视图', '关闭', '刷新'],
      backgroundColor: '#1a1d29',
      textColor: '#ffffff',
      textareaBorderColor: 'rgba(0, 212, 255, 0.3)',
    },
    magicType: {
      type: ['line', 'bar', 'stack'],
      title: {
        line: '切换为折线图',
        bar: '切换为柱状图',
        stack: '切换为堆叠',
      },
    },
    restore: {
      title: '还原',
    },
  },
  iconStyle: {
    borderColor: '#00d4ff',
  },
  emphasis: {
    iconStyle: {
      borderColor: '#00ffc8',
    },
  },
}
