<template>
  <div class="query-editor">
    <el-card class="editor-card">
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
            :rows="8"
            placeholder="请输入 SQL 查询语句"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleExecute" :loading="loading">执行查询</el-button>
          <el-button @click="handleExport" :disabled="!result">导出 Excel</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="result-card">
      <template #header>
        <h3>查询结果</h3>
      </template>
      <div v-if="result" class="result-container">
        <el-table :data="result.rows" max-height="500">
          <el-table-column
            v-for="(col, index) in result.columns"
            :key="index"
            :prop="index.toString()"
            :label="col"
          />
        </el-table>
        <div class="result-info">
          <p>执行时间: <strong>{{ result.execution_time_ms }}ms</strong></p>
          <p>行数: <strong>{{ result.total }}</strong></p>
        </div>
      </div>
      <div v-else class="empty-result">
        <el-empty description="暂无查询结果" />
      </div>
    </el-card>
  </div>
</template>

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
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.editor-card,
.result-card {
  width: 100%;
}

.editor-card :deep(.el-card__header) h3,
.result-card :deep(.el-card__header) h3 {
  margin: 0;
  font-size: 16px;
}

.editor-card :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.result-container {
  max-height: 600px;
  overflow-y: auto;
}

.result-info {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  display: flex;
  gap: 24px;
}

.result-info p {
  margin: 0;
  color: #606266;
  font-size: 13px;
}

.result-info p strong {
  color: #409eff;
}

.empty-result {
  padding: 40px 0;
}
</style>
