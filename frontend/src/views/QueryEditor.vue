<template>
  <div class="query-editor">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card>
            <template #header>
              <h3>SQL 编辑器</h3>
            </template>
            <el-form :model="queryForm" label-width="80px">
              <el-form-item label="数据源">
                <el-select v-model="queryForm.data_source_id" placeholder="请选择数据源">
                  <el-option
                    v-for="ds in dataSources"
                    :key="ds.id"
                    :label="ds.name"
                    :value="ds.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="SQL">
                <el-input
                  v-model="queryForm.sql"
                  type="textarea"
                  :rows="10"
                  placeholder="请输入 SQL 查询语句"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleExecute" :loading="loading">执行查询</el-button>
                <el-button @click="handleExport" :disabled="!result">导出 Excel</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>
              <h3>查询结果</h3>
            </template>
            <div v-if="result" class="result-container">
              <el-table :data="result.rows" max-height="400">
                <el-table-column
                  v-for="(col, index) in result.columns"
                  :key="index"
                  :prop="index.toString()"
                  :label="col"
                />
              </el-table>
              <div class="result-info">
                <p>执行时间: {{ result.execution_time_ms }}ms</p>
                <p>行数: {{ result.total }}</p>
              </div>
            </div>
            <div v-else class="empty-result">
              <p>暂无查询结果</p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div></template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDataSourceList } from '@/api/data_source'
import { executeSQL } from '@/api/query'
import { exportExcel } from '@/api/report'

export default {
  name: 'QueryEditor',
  components: { },
  setup() {
    const loading = ref(false)
    const dataSources = ref([])
    const queryForm = ref({
      data_source_id: null,
      sql: ''
    })
    const result = ref(null)

    const loadDataSources = async () => {
      try {
        dataSources.value = await getDataSourceList()
      } catch (error) {
        ElMessage.error('加载数据源失败')
      }
    }

    const handleExecute = async () => {
      if (!queryForm.value.data_source_id) {
        ElMessage.warning('请选择数据源')
        return
      }
      if (!queryForm.value.sql) {
        ElMessage.warning('请输入 SQL 查询语句')
        return
      }

      loading.value = true
      try {
        result.value = await executeSQL(queryForm.value)
        ElMessage.success('查询成功')
      } catch (error) {
        ElMessage.error('查询失败')
        result.value = null
      } finally {
        loading.value = false
      }
    }

    const handleExport = async () => {
      if (!result.value) {
        ElMessage.warning('暂无查询结果')
        return
      }

      try {
        const blob = await exportExcel({
          data_source_id: queryForm.value.data_source_id,
          sql: queryForm.value.sql,
          filename: 'export.xlsx'
        })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'export.xlsx'
        a.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('导出成功')
      } catch (error) {
        ElMessage.error('导出失败')
      }
    }

    onMounted(() => {
      loadDataSources()
    })

    return {
      loading,
      dataSources,
      queryForm,
      result,
      handleExecute,
      handleExport
    }
  }
}
</script>

<style scoped>
.query-editor {
  padding: 20px;
}

.result-container {
  max-height: 500px;
  overflow-y: auto;
}

.result-info {
  margin-top: 20px;
  padding: 10px;
  background: #f5f5f5;
  border-radius: 4px;
}

.result-info p {
  margin: 5px 0;
  color: #666;
}

.empty-result {
  text-align: center;
  padding: 50px 0;
  color: #999;
}
</style>