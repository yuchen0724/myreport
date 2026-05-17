<template>
  <div class="widget-slot" :class="`widget-${type}`">
    <!-- 编辑模式工具栏 -->
    <div v-if="isEditing" class="widget-toolbar">
      <span class="widget-title">{{ title }}</span>
      <el-button-group size="small">
        <el-tooltip content="编辑配置" placement="top">
          <el-button :icon="Setting" @click="$emit('edit')" />
        </el-tooltip>
        <el-tooltip content="删除组件" placement="top">
          <el-button type="danger" :icon="Delete" @click="$emit('remove')" />
        </el-tooltip>
      </el-button-group>
    </div>

    <!-- 主体内容，按类型动态渲染 -->
    <StatCard
      v-if="type === 'stat'"
      :widget="widget"
      :dashboard-data="dashboardData"
    />
    <ChartRenderer
      v-else-if="type === 'chart'"
      :chart-type="subtype || 'bar'"
      :data="chartData"
      :config="chartConfig"
      :show-toolbox="true"
    />
    <QueryResult
      v-else-if="type === 'table'"
      :result="tableResult"
      :loading="false"
    />
    <iframe
      v-else-if="type === 'iframe'"
      :src="iframeUrl"
      class="iframe-slot"
      frameborder="0"
    />
    <el-empty v-else description="未知组件类型" />
  </div>
</template>

<script>
import { ref, computed, watch, defineAsyncComponent, shallowRef } from "vue"
import { Setting, Delete } from "@element-plus/icons-vue"
import StatCard from "./DashboardWidget.vue"
import ChartRenderer from "./ChartRenderer.vue"
import QueryResult from "@/views/QueryResult.vue"

export default {
  name: "WidgetSlot",
  components: { StatCard, ChartRenderer, QueryResult, Setting, Delete },
  props: {
    widget: { type: Object, required: true },
    type: { type: String, required: true },
    subtype: { type: String, default: "" },
    title: { type: String, default: "" },
    isEditing: { type: Boolean, default: false },
    dashboardData: { type: Object, default: () => ({}) },
    extraConfig: { type: Object, default: () => ({}) },
  },
  emits: ["edit", "remove"],
  setup(props) {
    const chartData = ref(props.extraConfig?.chartData || [])
    const chartConfig = computed(() => ({
      title: props.title,
      height: "300px",
      ...(props.extraConfig?.chartConfig || {}),
    }))
    const tableResult = ref(props.extraConfig?.tableData || { columns: [], rows: [] })
    const iframeUrl = computed(() => props.extraConfig?.url || "")

    watch(
      () => props.extraConfig,
      (val) => {
        chartData.value = val?.chartData || []
        tableResult.value = val?.tableData || { columns: [], rows: [] }
      },
      { deep: true }
    )

    return { chartData, chartConfig, tableResult, iframeUrl, Setting, Delete }
  },
}
</script>

<style scoped>
.widget-slot {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.widget-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  border-radius: 4px 4px 0 0;
  flex-shrink: 0;
}
.widget-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.widget-slot > :not(.widget-toolbar) {
  flex: 1;
  overflow: auto;
}
.iframe-slot {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
