<template>
  <el-form label-width="100px">
    <el-form-item label="组件标题">
      <el-input v-model="form.title" placeholder="输入显示标题" />
    </el-form-item>
    <el-form-item label="数据绑定">
      <el-select v-model="form.widget_subtype" style="width:100%" @change="onSubtypeChange">
        <el-option label="数据源" value="data_source_count" />
        <el-option label="查询次数" value="query_count" />
        <el-option label="导出次数" value="export_count" />
        <el-option label="模板数量" value="template_count" />
        <el-option label="自定义 SQL" value="__custom_sql__" />
      </el-select>
    </el-form-item>

    <!-- 自定义 SQL 配置区域 -->
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
          :rows="4"
          placeholder="SELECT COUNT(*) FROM xxx"
          :disabled="!form.dataSourceId"
        />
      </el-form-item>
      <el-form-item label="预览值">
        <el-input v-model="form.expectedLabel" placeholder="可选，SQL 查询返回的数值标签（如 '销售总额'）" />
      </el-form-item>
    </template>
  </el-form>
</template>

<script>
import { reactive, watch, onMounted } from "vue"
import { getDataSourceList } from "@/api/data_source"

export default {
  name: "StatEditor",
  props: {
    widget: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const extra = props.widget.extra_config || {}
    const isCustom = props.widget.widget_subtype === '__custom_sql__' || extra.customSql

    const form = reactive({
      title: props.widget.title || "",
      widget_subtype: isCustom ? '__custom_sql__' : (props.widget.widget_subtype || props.widget.widget_type || "data_source_count"),
      dataSourceId: extra.dataSourceId || null,
      customSql: extra.customSql || "",
      expectedLabel: extra.expectedLabel || "",
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

    const onSubtypeChange = (val) => {
      if (val !== '__custom_sql__') {
        form.dataSourceId = null
        form.customSql = ""
        form.expectedLabel = ""
      }
    }

    watch(
      () => ({ ...form }),
      () => {
        // 构建 emit payload
        const payload = {
          title: form.title,
          widget_subtype: form.widget_subtype === '__custom_sql__' ? '__custom_sql__' : form.widget_subtype,
        }
        if (form.widget_subtype === '__custom_sql__') {
          payload.dataSourceId = form.dataSourceId
          payload.customSql = form.customSql
          payload.expectedLabel = form.expectedLabel
        }
        emit("update:modelValue", payload)
      },
      { deep: true }
    )

    return { form, dataSources, onSubtypeChange }
  },
}
</script>
