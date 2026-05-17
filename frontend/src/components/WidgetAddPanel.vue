<template>
  <div class="widget-add-panel">
    <h4 class="panel-title">添加组件</h4>

    <el-input
      v-model="searchQuery"
      placeholder="搜索组件..."
      size="small"
      clearable
      prefix-icon="Search"
      class="panel-search"
    />

    <div class="widget-categories">
      <div
        v-for="cat in filteredCategories"
        :key="cat.name"
        class="widget-category"
      >
        <div class="category-label">{{ cat.name }}</div>
        <div class="widget-list">
          <div
            v-for="item in cat.items"
            :key="item.type + (item.subtype || '')"
            class="widget-item"
            draggable="true"
            @dragstart="onDragStart($event, item)"
            @click="$emit('add', item)"
          >
            <el-icon :size="20" class="widget-icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="widget-label">{{ item.label }}</span>
          </div>
        </div>
      </div>
    </div>

    <el-button
      type="primary"
      size="small"
      class="apply-preset-btn"
      @click="$emit('showPresets')"
    >
      预设布局模板
    </el-button>
  </div>
</template>

<script>
import { ref, computed } from "vue"
import {
  DataAnalysis, TrendCharts, List, ChatLineSquare,
  Guide, Grid, PieChart, Histogram, Clock, Aim,
  Monitor, Promotion, Setting
} from "@element-plus/icons-vue"

const ALL_WIDGETS = [
  {
    name: "统计卡片",
    items: [
      { type: "stat", subtype: "data_source_count", label: "数据源", icon: "DataAnalysis", defaultW: 3, defaultH: 1 },
      { type: "stat", subtype: "query_count", label: "查询次数", icon: "TrendCharts", defaultW: 3, defaultH: 1 },
      { type: "stat", subtype: "export_count", label: "导出次数", icon: "Guide", defaultW: 3, defaultH: 1 },
      { type: "stat", subtype: "template_count", label: "模板数量", icon: "List", defaultW: 3, defaultH: 1 },
    ],
  },
  {
    name: "图表",
    items: [
      { type: "chart", subtype: "line", label: "折线图", icon: "TrendCharts", defaultW: 6, defaultH: 4 },
      { type: "chart", subtype: "bar", label: "柱状图", icon: "Histogram", defaultW: 6, defaultH: 4 },
      { type: "chart", subtype: "pie", label: "饼图", icon: "PieChart", defaultW: 4, defaultH: 4 },
      { type: "chart", subtype: "scatter", label: "散点图", icon: "Aim", defaultW: 6, defaultH: 4 },
      { type: "chart", subtype: "radar", label: "雷达图", icon: "Monitor", defaultW: 4, defaultH: 4 },
      { type: "chart", subtype: "gauge", label: "仪表盘", icon: "Clock", defaultW: 4, defaultH: 4 },
    ],
  },
  {
    name: "其他",
    items: [
      { type: "table", label: "数据表格", icon: "Grid", defaultW: 8, defaultH: 4 },
      { type: "nl2sql", label: "智能查询", icon: "ChatLineSquare", defaultW: 6, defaultH: 6 },
      { type: "iframe", label: "外部嵌入", icon: "Promotion", defaultW: 6, defaultH: 4 },
    ],
  },
]

export default {
  name: "WidgetAddPanel",
  components: {
    DataAnalysis, TrendCharts, List, ChatLineSquare,
    Guide, Grid, PieChart, Histogram, Clock, Aim,
    Monitor, Promotion, Setting
  },
  emits: ["add", "showPresets"],
  setup() {
    const searchQuery = ref("")

    const filteredCategories = computed(() => {
      if (!searchQuery.value) return ALL_WIDGETS
      const q = searchQuery.value.toLowerCase()
      return ALL_WIDGETS
        .map(cat => ({
          ...cat,
          items: cat.items.filter(item =>
            item.label.toLowerCase().includes(q) || item.type.includes(q)
          ),
        }))
        .filter(cat => cat.items.length > 0)
    })

    const onDragStart = (e, item) => {
      e.dataTransfer.setData("application/widget", JSON.stringify(item))
      e.dataTransfer.effectAllowed = "copy"
    }

    let counter = 0
    const createWidgetItem = (template) => ({
      i: `widget_${Date.now()}_${counter++}`,
      x: 0,
      y: 0,
      w: template.defaultW || 4,
      h: template.defaultH || 2,
      widget_type: template.type,
      widget_subtype: template.subtype || "",
      title: template.label,
      extra_config: {},
    })

    return { searchQuery, filteredCategories, onDragStart, createWidgetItem }
  },
}
</script>

<style scoped>
.widget-add-panel {
  padding: 16px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  min-width: 200px;
}
.panel-title {
  margin: 0 0 12px;
  font-size: 15px;
  color: #303133;
}
.panel-search {
  margin-bottom: 12px;
}
.widget-category {
  margin-bottom: 16px;
}
.category-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  padding-left: 4px;
}
.widget-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.widget-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.widget-item:hover {
  border-color: #409eff;
  color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}
.widget-item:active {
  cursor: grabbing;
}
.widget-icon {
  flex-shrink: 0;
}
.widget-label {
  font-size: 13px;
  white-space: nowrap;
}
.apply-preset-btn {
  width: 100%;
  margin-top: 8px;
}
</style>
