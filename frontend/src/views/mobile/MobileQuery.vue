<template>
  <div class="mobile-query">
    <!-- 顶部标题 -->
    <div class="mobile-page-header">
      <h2>SQL 查询</h2>
    </div>

    <!-- 查询表单 -->
    <div class="query-form-card">
      <el-form :model="queryForm" label-position="top">
        <el-form-item label="数据源">
          <el-select
            v-model="queryForm.data_source_id"
            placeholder="请选择数据源"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="ds in dataSources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="SQL 方言">
          <DialectSelector
            v-model="queryForm.dialect"
            placeholder="选择 SQL 方言"
            width="100%"
          />
        </el-form-item>

        <el-form-item label="SQL 语句">
          <el-input
            v-model="queryForm.sql"
            type="textarea"
            :rows="6"
            placeholder="输入 SQL 查询语句&#10;使用 ${xxx} 语法添加参数占位符"
          />
        </el-form-item>

        <!-- 参数化查询 -->
        <template v-if="extractedParams.length > 0">
          <el-divider content-position="left">
            <el-tag size="small" type="info">查询参数</el-tag>
          </el-divider>
          <el-form-item
            v-for="param in extractedParams"
            :key="param"
            :label="param"
          >
            <el-input
              v-model="paramValues[param]"
              :placeholder="`请输入 ${param} 的值`"
              clearable
            />
          </el-form-item>
        </template>

        <el-form-item>
          <div class="button-group">
            <el-button
              type="primary"
              @click="handleExecute"
              :loading="loading"
              style="flex: 1"
            >
              执行查询
            </el-button>
            <el-button
              @click="handleExport"
              :disabled="!result"
              :loading="exporting"
              style="flex: 1"
            >
              导出
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <!-- 错误信息 -->
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      @close="errorMessage = ''"
      class="error-alert"
    />

    <!-- 查询结果 -->
    <div v-if="result" class="result-section">
      <div class="result-header">
        <span>查询结果</span>
        <div class="result-meta">
          <el-tag size="small" type="info">{{ result.execution_time_ms }}ms</el-tag>
          <el-tag size="small">{{ result.total }} 条</el-tag>
        </div>
      </div>

      <!-- 移动端友好的结果表格（横向滚动） -->
      <div class="result-table-wrapper">
        <table class="mobile-result-table">
          <thead>
            <tr>
              <th v-for="col in result.columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in paginatedRows" :key="idx">
              <td v-for="(col, ci) in result.columns" :key="ci">
                {{ row[ci] ?? '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="result-pagination">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="result.total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="handlePageChange"
          small
        />
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && !errorMessage" class="empty-state">
      <el-empty description="执行查询后结果将显示在这里" :image-size="80" />
    </div>

    <!-- 查询历史抽屉 -->
    <el-drawer
      v-model="historyDrawerVisible"
      title="查询历史"
      size="80%"
      direction="ltr"
    >
      <div class="history-list">
        <div
          v-for="(item, index) in queryHistory"
          :key="index"
          class="history-item"
          @click="selectHistory(item)"
        >
          <div class="history-sql">{{ item.sql?.substring(0, 100) }}{{ item.sql?.length > 100 ? '...' : '' }}</div>
          <div class="history-meta">
            <span>{{ item.data_source_name || '数据源#' + item.data_source_id }}</span>
            <span>{{ formatTime(item.created_at) }}</span>
          </div>
        </div>
        <el-empty v-if="queryHistory.length === 0" description="暂无查询历史" :image-size="60" />
      </div>
    </el-drawer>

    <!-- 浮动历史按钮 -->
    <div class="fab-history" @click="historyDrawerVisible = true">
      <el-icon :size="20"><Clock /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock } from '@element-plus/icons-vue'
import { getDataSourceList } from '@/api/data_source'
import { executeSQL, getQueryHistory } from '@/api/query'
import DialectSelector from '@/components/DialectSelector.vue'

const loading = ref(false)
const dataSources = ref([])
const result = ref(null)
const errorMessage = ref('')
const exporting = ref(false)

const queryForm = ref({
  data_source_id: null,
  sql: '',
  dialect: ''
})

// 分页
const currentPage = ref(1)
const pageSize = ref(20)

const paginatedRows = computed(() => {
  if (!result.value?.rows) return []
  // 移动端简化：使用服务端分页
  return result.value.rows
})

// 参数化查询
const paramValues = ref({})
const extractedParams = ref([])

function extractParams(sql) {
  const params = []
  const regex = /\$\{(\w+)\}/g
  let match
  while ((match = regex.exec(sql)) !== null) {
    if (!params.includes(match[1])) params.push(match[1])
  }
  return params
}

watch(() => queryForm.value.sql, (sql) => {
  const params = extractParams(sql || '')
  extractedParams.value = params
  const newValues = { ...paramValues.value }
  params.forEach(p => {
    if (!(p in newValues)) newValues[p] = ''
  })
  Object.keys(newValues).forEach(k => {
    if (!params.includes(k)) delete newValues[k]
  })
  paramValues.value = newValues
})

// 数据源加载
const loadDataSources = async () => {
  try {
    dataSources.value = await getDataSourceList()
  } catch {
    ElMessage.error('加载数据源失败')
  }
}

// 执行查询
const handleExecute = async () => {
  if (!queryForm.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!queryForm.value.sql?.trim()) {
    ElMessage.warning('请输入 SQL 查询语句')
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    let sql = queryForm.value.sql
    for (const key of Object.keys(paramValues.value)) {
      const val = paramValues.value[key]
      if (val !== undefined && val !== null && val !== '') {
        sql = sql.replace(new RegExp(`\\$\\{${key}\\}`, 'g'), val)
      }
    }

    const payload = {
      data_source_id: queryForm.value.data_source_id,
      sql,
      page: currentPage.value,
      page_size: pageSize.value
    }

    if (queryForm.value.dialect) {
      payload.dialect = queryForm.value.dialect
    }

    result.value = await executeSQL(payload)
    currentPage.value = result.value.page || 1
    ElMessage.success('查询成功')
  } catch (error) {
    const msg = error.response?.data?.detail || error.message || '查询失败'
    errorMessage.value = msg
    ElMessage.error(msg)
    result.value = null
  } finally {
    loading.value = false
  }
}

// 分页
const handlePageChange = (page) => {
  currentPage.value = page
  handleExecute()
}

// 导出（移动端简化：仅导出 Excel）
const handleExport = async () => {
  if (!result.value) {
    ElMessage.warning('暂无查询结果')
    return
  }
  exporting.value = true
  try {
    const { exportExcel } = await import('@/api/report')
    const response = await exportExcel({
      data_source_id: queryForm.value.data_source_id,
      sql: queryForm.value.sql,
      filename: `query_export_${Date.now()}.xlsx`
    })
    const blob = new Blob([response], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `query_export_${Date.now()}.xlsx`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败：' + (error.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}

// 查询历史
const historyDrawerVisible = ref(false)
const queryHistory = ref([])

const loadQueryHistory = async () => {
  try {
    const res = await getQueryHistory({ page: 1, page_size: 20 })
    queryHistory.value = Array.isArray(res) ? res : (res.items || res.records || [])
  } catch {
    // 静默
  }
}

const selectHistory = (item) => {
  queryForm.value.data_source_id = item.data_source_id
  queryForm.value.sql = item.sql
  historyDrawerVisible.value = false
  ElMessage.info('已填入历史查询')
}

function formatTime(timeStr) {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    const pad = n => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return timeStr
  }
}

onMounted(() => {
  loadDataSources()
  loadQueryHistory()
})
</script>

<style scoped>
.mobile-query {
  padding: 16px;
  padding-bottom: 80px;
}

.mobile-page-header {
  margin-bottom: 16px;
}

.mobile-page-header h2 {
  font-size: 22px;
  font-weight: 600;
  margin: 0;
}

.query-form-card {
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.button-group {
  display: flex;
  gap: 8px;
  width: 100%;
}

.error-alert {
  margin-top: 12px;
}

.result-section {
  margin-top: 16px;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
}

.result-meta {
  display: flex;
  gap: 6px;
}

.result-table-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin: 0 -16px;
  padding: 0 16px;
}

.mobile-result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  white-space: nowrap;
  min-width: 400px;
}

.mobile-result-table th {
  background: var(--bg-secondary, #f5f7fa);
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  position: sticky;
  top: 0;
}

.mobile-result-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-color, #ebeef5);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-pagination {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}

.empty-state {
  margin-top: 40px;
}

/* 浮动历史按钮 */
.fab-history {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--bg-header, #409eff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
  cursor: pointer;
  z-index: 100;
}

.fab-history:active {
  transform: scale(0.95);
}

/* 抽屉历史列表 */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  padding: 12px;
  background: var(--bg-secondary, #f5f7fa);
  border-radius: 8px;
  cursor: pointer;
}

.history-item:active {
  background: var(--border-color, #e4e7ed);
}

.history-sql {
  font-size: 13px;
  margin-bottom: 6px;
  font-family: monospace;
  line-height: 1.4;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
</style>
