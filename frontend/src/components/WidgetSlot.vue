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
      :chart-type="effectiveChartType"
      :data="chartData"
      :config="chartConfig"
      :show-toolbox="true"
    />
    <QueryResult
      v-else-if="type === 'table'"
      :result="tableResult"
      :loading="tableLoading"
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
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue"
import { Setting, Delete } from "@element-plus/icons-vue"
import StatCard from "./DashboardWidget.vue"
import ChartRenderer from "./ChartRenderer.vue"
import QueryResult from "@/views/QueryResult.vue"
import { executeSQL } from "@/api/query"

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
    // ——— 图表数据 ———
    const chartData = ref(props.extraConfig?.chartData || [])
    const customChartData = ref([])
    const chartDataLoaded = ref(false)

    const isCustomSqlChart = computed(() => {
      return props.subtype === '__custom_sql__' && props.extraConfig?.customSql && props.extraConfig?.dataSourceId
    })

    const effectiveChartType = computed(() => {
      if (isCustomSqlChart.value) {
        return props.extraConfig?.chartSubType || 'bar'
      }
      return props.subtype || 'bar'
    })

    const chartConfig = computed(() => {
      const extra = props.extraConfig || {}
      return {
        title: extra.chartTitle || props.title,
        height: "300px",
        x_axis: extra.xAxis || "x",
        y_axis: extra.yAxis || "y",
        ...(extra.chartConfig || {}),
      }
    })

    // ——— 表格数据 ———
    const tableResult = ref(props.extraConfig?.tableData || { columns: [], rows: [] })
    const tableLoading = ref(false)
    let tablePollTimer = null

    const isCustomSqlTable = computed(() => {
      return props.extraConfig?.dataSourceId && props.extraConfig?.customSql
    })

    // ——— 自定义 SQL 执行（图表 + 表格共用） ———
    const fetchCustomSqlData = async () => {
      const extra = props.extraConfig || {}

      if (!extra.dataSourceId || !extra.customSql) {
        return
      }

      try {
        const res = await executeSQL({
          data_source_id: extra.dataSourceId,
          sql: extra.customSql,
          page: 1,
          page_size: 5000,
          skip_deep_pagination_check: true,
        })
        const data = res.data || res

        if (props.type === 'chart') {
          // 图表：将 SQL 结果转为 {x, y} 格式
          const xAxis = extra.xAxis || 'x'
          const yAxis = extra.yAxis || 'y'
          const rows = data.rows || []
          const cols = data.columns || []

          // 找到 x 和 y 列的索引
          const xIdx = cols.indexOf(xAxis)
          const yIdx = cols.indexOf(yAxis)
          const rowIdx = cols.indexOf('row') !== -1 ? cols.indexOf('row') : -1

          if (xIdx !== -1 && yIdx !== -1) {
            customChartData.value = rows.map(row => ({
              x: row[xIdx] !== null && row[xIdx] !== undefined ? String(row[xIdx]) : '',
              y: row[yIdx] !== null && row[yIdx] !== undefined ? Number(row[yIdx]) : 0,
            }))
          } else if (cols.length >= 2) {
            // 自动推定：第一列 x，第二列 y
            customChartData.value = rows.map(row => ({
              x: row[0] !== null ? String(row[0]) : '',
              y: Number(row[1]) || 0,
            }))
          }
          chartDataLoaded.value = true
        } else if (props.type === 'table') {
          // 表格：直接使用 SQL 结果
          tableResult.value = {
            columns: data.columns || [],
            rows: data.rows || [],
            total: data.total || 0,
          }
        }
      } catch (e) {
        console.error(`[WidgetSlot] 自定义 SQL 查询失败 (${props.type}):`, e)
        if (props.type === 'table') {
          tableResult.value = {
            columns: [],
            rows: [],
            error: e?.response?.data?.detail || e?.message || '查询失败',
          }
        }
      } finally {
        if (props.type === 'table') {
          tableLoading.value = false
        }
      }
    }

    // ——— 监控 extraConfig 变化 ———
    watch(
      () => props.extraConfig,
      (val) => {
        chartData.value = val?.chartData || []
        if (props.type === 'chart' && !isCustomSqlChart.value) {
          // 非自定义 SQL 的图表：保留从 dashboardData 注入的 chartData
          customChartData.value = []
          chartDataLoaded.value = false
        }

        // 自定义 SQL 变化时重新查询
        if (isCustomSqlChart.value || isCustomSqlTable.value) {
          if (props.type === 'table') {
            tableLoading.value = true
          }
          fetchCustomSqlData()
        }
      },
      { deep: true }
    )

    // ——— 初始加载 ———
    onMounted(() => {
      if (isCustomSqlChart.value || isCustomSqlTable.value) {
        if (props.type === 'table') {
          tableLoading.value = true
        }
        fetchCustomSqlData()
      }
    })

    // ——— 返回值 ———
    // 如果是自定义 SQL 图表，chartData 用 customChartData
    const finalChartData = computed(() => isCustomSqlChart.value ? customChartData.value : chartData.value)

    const iframeUrl = computed(() => props.extraConfig?.url || "")

    return {
      effectiveChartType,
      chartData: finalChartData,
      chartConfig,
      tableResult,
      tableLoading,
      iframeUrl,
      Setting, Delete,
    }
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
