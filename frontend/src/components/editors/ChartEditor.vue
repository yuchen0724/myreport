<template>
  <el-form label-width="100px">
    <el-form-item label="组件标题">
      <el-input v-model="form.title" placeholder="输入显示标题" />
    </el-form-item>
    <el-form-item label="图表类型">
      <el-select v-model="form.widget_subtype" style="width:100%" @change="onTypeChange">
        <el-option label="折线图" value="line" />
        <el-option label="柱状图" value="bar" />
        <el-option label="饼图" value="pie" />
        <el-option label="散点图" value="scatter" />
        <el-option label="雷达图" value="radar" />
        <el-option label="仪表盘" value="gauge" />
        <el-option label="自定义图表 SQL" value="__custom_sql__" />
      </el-select>
    </el-form-item>

    <!-- 内置图表选项 -->
    <template v-if="form.widget_subtype !== '__custom_sql__'">
      <el-form-item label="图表标题">
        <el-input v-model="form.chartTitle" placeholder="图表内部标题" />
      </el-form-item>
      <el-form-item label="X 轴字段">
        <el-input v-model="form.xAxis" placeholder="数据中的 x 字段" />
      </el-form-item>
      <el-form-item label="Y 轴字段">
        <el-input v-model="form.yAxis" placeholder="数据中的 y 字段" />
      </el-form-item>
    </template>

    <!-- 自定义 SQL 配置 -->
    <template v-if="form.widget_subtype === '__custom_sql__'">
      <el-form-item label="数据源">
        <el-select v-model="form.dataSourceId" style="width:100%" placeholder="选择数据源">
          <el-option
            v-for="ds in dataSources"
            :key="ds.id"
            :label="ds.name"
            :value="ds.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="查询 SQL">
        <el-input
          v-model="form.customSql"
          type="textarea"
          :rows="5"
          placeholder="SELECT date AS x, amount AS y FROM orders GROUP BY date ORDER BY date"
          :disabled="!form.dataSourceId"
        />
      </el-form-item>
      <el-form-item label="图表子类型">
        <el-select v-model="form.chartSubType" style="width:100%">
          <el-option label="折线图" value="line" />
          <el-option label="柱状图" value="bar" />
          <el-option label="饼图" value="pie" />
        </el-select>
      </el-form-item>
      <el-form-item label="X 轴字段">
        <el-input v-model="form.xAxis" placeholder="SQL 结果集中作为 X 轴的列名（如 date）" />
      </el-form-item>
      <el-form-item label="Y 轴字段">
        <el-input v-model="form.yAxis" placeholder="SQL 结果集中作为 Y 轴的列名（如 amount）" />
      </el-form-item>
    </template>
  </el-form>
</template>

<script>
import { reactive, watch, onMounted } from "vue"
import { getDataSourceList } from "@/api/data_source"

export default {
  name: "ChartEditor",
  props: {
    widget: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const extra = props.widget.extra_config || {}
    const isCustom = props.widget.widget_subtype === '__custom_sql__' || extra.customSql

    const form = reactive({
      title: props.widget.title || "",
      widget_subtype: isCustom ? '__custom_sql__' : (props.widget.widget_subtype || "bar"),
      chartTitle: extra.chartTitle || "",
      xAxis: extra.xAxis || "",
      yAxis: extra.yAxis || "",
      // 自定义 SQL 字段
      dataSourceId: extra.dataSourceId || null,
      customSql: extra.customSql || "",
      chartSubType: extra.chartSubType || "bar",
    })

    const dataSources = reactive([])

    onMounted(async () => {
      try {
        const res = await getDataSourceList()
        dataSources.push(...(res.data || res || []))
      } catch (e) {
        console.error("加载数据源列表失败:", e)
      }
    })

    const onTypeChange = (val) => {
      if (val !== '__custom_sql__') {
        form.dataSourceId = null
        form.customSql = ""
        form.chartSubType = "bar"
      }
    }

    watch(
      () => ({ ...form }),
      () => {
        const payload = {
          title: form.title,
          widget_subtype: form.widget_subtype,
          chartTitle: form.chartTitle,
          xAxis: form.xAxis,
          yAxis: form.yAxis,
          // 自定义 SQL 字段也放在 extra 中
          dataSourceId: form.dataSourceId,
          customSql: form.customSql,
          chartSubType: form.chartSubType,
        }
        emit("update:modelValue", payload)
      },
      { deep: true }
    )

    return { form, dataSources, onTypeChange }
  },
}
</script>
