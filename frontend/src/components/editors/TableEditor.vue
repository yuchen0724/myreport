<template>
  <el-form label-width="100px">
    <el-form-item label="组件标题">
      <el-input v-model="form.title" placeholder="输入显示标题" />
    </el-form-item>
    <el-form-item label="数据来源">
      <el-select v-model="form.dataMode" style="width:100%" @change="onModeChange">
        <el-option label="手动输入 SQL" value="sql" />
        <el-option label="自定义数据源 + SQL" value="custom" />
      </el-select>
    </el-form-item>

    <!-- 手动 SQL 模式（向后兼容） -->
    <template v-if="form.dataMode === 'sql'">
      <el-form-item label="查询 SQL">
        <el-input v-model="form.querySql" type="textarea" :rows="4" placeholder="SELECT ..." />
      </el-form-item>
    </template>

    <!-- 自定义数据源模式 -->
    <template v-if="form.dataMode === 'custom'">
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
          placeholder="SELECT col1, col2, col3 FROM your_table WHERE ..."
          :disabled="!form.dataSourceId"
        />
      </el-form-item>
    </template>
  </el-form>
</template>

<script>
import { reactive, watch, onMounted } from "vue"
import { getDataSourceList } from "@/api/data_source"

export default {
  name: "TableEditor",
  props: {
    widget: { type: Object, required: true },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const extra = props.widget.extra_config || {}

    // 判断当前数据模式
    let mode = 'sql'
    if (extra.dataSourceId && extra.customSql) {
      mode = 'custom'
    }

    const form = reactive({
      title: props.widget.title || "",
      dataMode: mode,
      querySql: extra.querySql || "",
      // 自定义数据源字段
      dataSourceId: extra.dataSourceId || null,
      customSql: extra.customSql || "",
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

    const onModeChange = (val) => {
      if (val === 'sql') {
        form.dataSourceId = null
        form.customSql = ""
      } else {
        form.querySql = ""
      }
    }

    watch(
      () => ({ ...form }),
      () => {
        const payload = {
          title: form.title,
          querySql: form.querySql,
          dataSourceId: form.dataSourceId,
          customSql: form.customSql,
        }
        emit("update:modelValue", payload)
      },
      { deep: true }
    )

    return { form, dataSources, onModeChange }
  },
}
</script>
