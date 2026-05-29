<template>
  <el-dialog
    v-model="visible"
    :title="`编辑${titlePrefix} — ${dialogTitle}`"
    width="500px"
    @closed="handleClosed"
  >
    <component
      :is="editorComponent"
      :key="editorKey"
      :widget="currentWidget"
      @update:modelValue="onFormUpdate"
    />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script>
import { ref, computed, markRaw, watch } from "vue"
import { ElMessage } from "element-plus"
import StatEditor from "./editors/StatEditor.vue"
import ChartEditor from "./editors/ChartEditor.vue"
import TableEditor from "./editors/TableEditor.vue"
import Nl2sqlEditor from "./editors/Nl2sqlEditor.vue"
import IframeEditor from "./editors/IframeEditor.vue"
import SemanticMetricWidgetEditor from "./editors/SemanticMetricWidgetEditor.vue"

const EDITOR_MAP = {
  stat: markRaw(StatEditor),
  chart: markRaw(ChartEditor),
  table: markRaw(TableEditor),
  nl2sql: markRaw(Nl2sqlEditor),
  iframe: markRaw(IframeEditor),
}

export default {
  name: "WidgetEditorDialog",
  components: { StatEditor, ChartEditor, TableEditor, Nl2sqlEditor, IframeEditor, SemanticMetricWidgetEditor },
  props: {
    modelValue: { type: Boolean, default: false },
    widget: { type: Object, default: null },
  },
  emits: ["update:modelValue", "saved"],
  setup(props, { emit }) {
    const visible = computed({
      get: () => props.modelValue,
      set: (v) => emit("update:modelValue", v),
    })
    const saving = ref(false)
    const formData = ref({})
    const editorKey = ref(0)

    const currentWidget = computed(() => props.widget)

    const dialogTitle = computed(() => props.widget?.title || "未命名")

    const editorComponent = computed(() => {
      if (!props.widget) return null
      if (
        props.widget.widget_type === 'chart' &&
        (props.widget.widget_subtype === '__semantic_metric__' || props.widget.extra_config?.semanticMetricQuery)
      ) {
        return markRaw(SemanticMetricWidgetEditor)
      }
      return EDITOR_MAP[props.widget.widget_type] || null
    })

    const titlePrefix = computed(() => {
      const names = { stat: "统计卡片", chart: "图表", table: "数据表格", nl2sql: "智能查询", iframe: "外部嵌入" }
      if (props.widget?.widget_subtype === '__semantic_metric__' || props.widget?.extra_config?.semanticMetricQuery) {
        return "语义指标图表"
      }
      return names[props.widget?.widget_type] || "组件"
    })

    const onFormUpdate = (data) => {
      formData.value = data
    }

    const handleSave = async () => {
      if (!props.widget || !formData.value) return
      saving.value = true
      try {
        const { updateWidget } = await import("@/api/dashboard")
        const payload = {
          title: formData.value.title,
        }

        // 处理 widget_subtype（stat 和 chart 有）
        if (formData.value.widget_subtype !== undefined) {
          payload.widget_subtype = formData.value.widget_subtype
        }

        // 构建 extra_config — 保留未被编辑的字段
        const extra = { ...(props.widget.extra_config || {}) }
        // 覆盖编辑过的字段
        if (formData.value.url !== undefined) extra.url = formData.value.url
        if (formData.value.querySql !== undefined) extra.querySql = formData.value.querySql
        if (formData.value.chartTitle !== undefined) extra.chartTitle = formData.value.chartTitle
        // 自定义 SQL 统计卡片字段
        if (formData.value.dataSourceId !== undefined) extra.dataSourceId = formData.value.dataSourceId
        if (formData.value.customSql !== undefined) extra.customSql = formData.value.customSql
        if (formData.value.expectedLabel !== undefined) extra.expectedLabel = formData.value.expectedLabel
        // 图表自定义 SQL 字段
        if (formData.value.xAxis !== undefined) extra.xAxis = formData.value.xAxis
        if (formData.value.yAxis !== undefined) extra.yAxis = formData.value.yAxis
        if (formData.value.chartSubType !== undefined) extra.chartSubType = formData.value.chartSubType
        if (formData.value.semanticMetricQuery !== undefined) extra.semanticMetricQuery = formData.value.semanticMetricQuery
        payload.extra_config = extra

        // 解析 widgetId
        const widgetId = parseInt(props.widget.i?.split("_")[1], 10)
        if (!widgetId) {
          ElMessage.warning("组件尚未保存，请先保存整个布局")
          saving.value = false
          return
        }

        // 需要 layoutId — 由父组件通过 saved 事件携带
        emit("saved", { widgetId, payload })
        visible.value = false
      } catch (err) {
        console.error("保存组件配置失败:", err)
        ElMessage.error("保存失败")
      } finally {
        saving.value = false
      }
    }

    const handleClosed = () => {
      formData.value = {}
    }

    // Dialog 打开时递增 key 强制重建子组件，确保初始值来自最新 widget
    watch(() => props.modelValue, (val) => {
      if (val) {
        editorKey.value++
      }
    })

    return { visible, saving, formData, currentWidget, dialogTitle, editorComponent, titlePrefix, onFormUpdate, handleSave, handleClosed, editorKey }
  },
}
</script>
