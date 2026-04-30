<!-- frontend/src/views/NL2SQLEditor.vue -->
<template>
  <div class="nl2sql-editor">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>NL2SQL 查询</span>
          </div>
        </template>

      <el-form :model="form" label-width="120px">
        <el-form-item label="数据源">
          <el-select v-model="form.data_source_id" placeholder="请选择数据源">
            <el-option
              v-for="ds in dataSources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="自然语言问题">
          <el-input
            v-model="form.question"
            type="textarea"
            :rows="3"
            placeholder="请输入自然语言问题，例如：查询用户表中的前10条记录"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleParse" :loading="loading">
            解析并执行
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </el-form-item>
      </el-form>

      <!-- SQL 建议 -->
      <div v-if="suggestions.length > 0" class="suggestions">
        <h4>SQL 建议</h4>
        <el-table :data="suggestions" style="width: 100%">
          <el-table-column prop="sql" label="SQL" />
          <el-table-column prop="confidence" label="置信度" width="120">
            <template #default="{ row }">
              {{ (row.confidence * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="explanation" label="解释" />
        </el-table>
      </div>

      <!-- 查询结果 -->
      <div v-if="queryResult" class="query-result">
        <h4>查询结果</h4>
        <el-table :data="queryResult.rows" style="width: 100%">
          <el-table-column
            v-for="(column, index) in queryResult.columns"
            :key="index"
            :prop="index.toString()"
            :label="column"
          />
        </el-table>
        <div class="result-info">
          <span>共 {{ queryResult.total }} 条记录</span>
          <span>执行时间：{{ executionTimeMs }}ms</span>
        </div>
      </div>
    </el-card>
  </div></template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { parseQuestion } from '@/api/nl2sql'
import { getDataSourceList } from '@/api/data_source'
const form = ref({
  data_source_id: null,
  question: ''
})

const dataSources = ref([])
const suggestions = ref([])
const queryResult = ref(null)
const executionTimeMs = ref(null)
const loading = ref(false)

onMounted(async () => {
  await loadDataSources()
})

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSources.value = response
  } catch (error) {
    ElMessage.error('加载数据源失败')
  }
}

const handleParse = async () => {
  if (!form.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.question) {
    ElMessage.warning('请输入自然语言问题')
    return
  }

  loading.value = true
  try {
    const response = await parseQuestion(form.value)
    suggestions.value = response.suggestions
    queryResult.value = response.query_result
    executionTimeMs.value = response.execution_time_ms
    ElMessage.success('解析成功')
  } catch (error) {
    ElMessage.error('解析失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleClear = () => {
  form.value.question = ''
  suggestions.value = []
  queryResult.value = null
  executionTimeMs.value = null
}
</script>

<style scoped>
.nl2sql-editor {
  padding: 20px;
}

.suggestions,
.query-result {
  margin-top: 20px;
}

.suggestions h4,
.query-result h4 {
  margin-bottom: 10px;
}

.result-info {
  margin-top: 10px;
  color: #666;
}

.result-info span {
  margin-right: 20px;
}
</style>
