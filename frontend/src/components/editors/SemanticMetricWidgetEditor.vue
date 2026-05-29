<template>
  <el-form label-width="100px">
    <el-form-item label="组件标题">
      <el-input v-model="form.title" />
    </el-form-item>

    <el-form-item label="指标">
      <el-select v-model="form.metric_key" style="width: 100%" filterable @change="handleMetricChange">
        <el-option
          v-for="metric in metrics"
          :key="metric.metric_key"
          :label="`${metric.name} (${metric.metric_key})`"
          :value="metric.metric_key"
        />
      </el-select>
    </el-form-item>

    <el-form-item label="图表类型">
      <el-radio-group v-model="form.chartSubType">
        <el-radio-button label="bar">柱状图</el-radio-button>
        <el-radio-button label="line">折线图</el-radio-button>
      </el-radio-group>
    </el-form-item>

    <el-form-item label="维度">
      <el-select v-model="form.dimensions" multiple style="width: 100%">
        <el-option
          v-for="dimension in currentMetricDimensions"
          :key="dimension"
          :label="dimension"
          :value="dimension"
        />
      </el-select>
    </el-form-item>

    <el-form-item label="时间范围">
      <el-date-picker
        v-model="form.dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        unlink-panels
      />
    </el-form-item>

    <el-form-item label="过滤条件">
      <div class="filter-list">
        <div
          v-for="(filter, index) in form.filterRows"
          :key="filter.id"
          class="filter-row"
        >
          <el-select v-model="filter.field" placeholder="字段" filterable>
            <el-option
              v-for="field in filterFields"
              :key="field"
              :label="field"
              :value="field"
            />
          </el-select>
          <el-input v-model="filter.value" placeholder="值" />
          <el-button @click="removeFilterRow(index)">删除</el-button>
        </div>
        <el-button @click="addFilterRow">添加条件</el-button>
      </div>
    </el-form-item>

    <el-form-item label="分页">
      <div class="page-row">
        <el-input-number v-model="form.page" :min="1" />
        <el-input-number v-model="form.page_size" :min="1" :max="1000" />
      </div>
    </el-form-item>
  </el-form>
</template>

<script>
import { computed, onMounted, reactive, watch } from "vue"
import { getSemanticMetrics } from "@/api/semanticMetric"

export default {
  name: "SemanticMetricWidgetEditor",
  props: {
    widget: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const extra = props.widget.extra_config || {}
    const query = extra.semanticMetricQuery || {}
    let filterRowSeed = 0

    const form = reactive({
      title: props.widget.title || "",
      metric_key: query.metric_key || "",
      chartSubType: extra.chartSubType || "bar",
      dateRange: [query.start_time, query.end_time].filter(Boolean),
      dimensions: [...(query.dimensions || [])],
      filterRows: Object.entries(query.filters || {}).map(([field, value]) => ({
        id: ++filterRowSeed,
        field,
        value,
      })),
      page: query.page || 1,
      page_size: query.page_size || 50,
    })

    const metrics = reactive([])

    const currentMetric = computed(() => metrics.find(metric => metric.metric_key === form.metric_key) || null)
    const currentMetricDimensions = computed(() => currentMetric.value?.dimensions || [])
    const filterFields = computed(() => {
      if (!currentMetric.value) return []
      return [currentMetric.value.time_column, ...(currentMetric.value.dimensions || [])]
    })

    const buildPayload = () => {
      const filters = {}
      form.filterRows.forEach((filter) => {
        if (filter.field && filter.value !== "") {
          filters[filter.field] = filter.value
        }
      })
      const [startTime, endTime] = form.dateRange || []
      const xAxis = form.dimensions[0] || currentMetric.value?.dimensions?.[0] || ""
      return {
        title: form.title,
        widget_subtype: "__semantic_metric__",
        chartSubType: form.chartSubType,
        xAxis,
        yAxis: "metric_value",
        chartTitle: form.title,
        semanticMetricQuery: {
          metric_key: form.metric_key,
          start_time: startTime || null,
          end_time: endTime || null,
          dimensions: form.dimensions,
          filters,
          page: form.page,
          page_size: form.page_size,
        },
      }
    }

    const emitUpdate = () => {
      emit("update:modelValue", buildPayload())
    }

    const handleMetricChange = () => {
      form.dimensions = [...currentMetricDimensions.value]
      form.filterRows = []
    }

    const addFilterRow = () => {
      form.filterRows.push({ id: ++filterRowSeed, field: "", value: "" })
    }

    const removeFilterRow = (index) => {
      form.filterRows.splice(index, 1)
    }

    onMounted(async () => {
      try {
        const result = await getSemanticMetrics({ active_only: true })
        metrics.push(...(result || []))
        if (!form.metric_key && metrics.length) {
          form.metric_key = metrics[0].metric_key
          form.dimensions = [...(metrics[0].dimensions || [])]
        }
        emitUpdate()
      } catch (error) {
        console.error("加载语义指标失败:", error)
      }
    })

    watch(
      () => ({ ...form, filterRows: form.filterRows.map(row => ({ ...row })) }),
      emitUpdate,
      { deep: true }
    )

    return {
      form,
      metrics,
      currentMetricDimensions,
      filterFields,
      handleMetricChange,
      addFilterRow,
      removeFilterRow,
    }
  },
}
</script>

<style scoped>
.filter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.filter-row {
  display: grid;
  grid-template-columns: minmax(140px, 180px) 1fr 52px;
  gap: 8px;
}

.page-row {
  display: flex;
  gap: 8px;
}
</style>
