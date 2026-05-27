<template>
  <div class="query-editor-page">
    <!-- 左侧查询历史侧边栏按钮 -->
    <div class="sidebar-toggle">
      <el-button
        type="default"
        size="small"
        :icon="Clock"
        @click="historyDrawerVisible = true"
      >
        查询历史
      </el-button>
    </div>

    <div class="editor-layout">
      <!-- 编辑器区域 -->
      <div class="editor-main">
        <el-card class="editor-card">
          <template #header>
            <div class="editor-header">
              <h3>
                <el-icon><Connection /></el-icon>
                SQL 编辑器
              </h3>
              <div class="header-tags">
                <el-tag v-if="result && result.cache_hit" type="success" size="small">
                  <el-icon><Timer /></el-icon> 缓存命中
                </el-tag>
                <el-tag v-if="result && result.suggest_async" type="warning" size="small">
                  <el-icon><Warning /></el-icon> 建议异步导出
                </el-tag>
              </div>
            </div>
          </template>

          <el-form :model="queryForm" label-width="80px">
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
                width="240px"
              />
            </el-form-item>

            <el-form-item label="SQL">
              <el-input
                ref="sqlInputRef"
                v-model="queryForm.sql"
                type="textarea"
                :rows="8"
                placeholder="输入 SQL 查询语句（Ctrl+Enter 执行）&#10;使用 ${xxx} 语法添加参数占位符"
              />
            </el-form-item>

            <!-- 参数化查询：自动提取占位符 -->
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
              <el-button
                type="primary"
                @click="handleExecute"
                :loading="loading"
                :icon="DocumentCopy"
              >
                执行查询
              </el-button>
              <el-button
                @click="handleExportExcel"
                :disabled="!result"
                :loading="exportingExcel"
                :icon="Download"
              >
                导出 Excel
              </el-button>
              <el-button
                @click="handleExportPDF"
                :disabled="!result"
                :loading="exportingPDF"
                :icon="Download"
              >
                导出 PDF
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 错误信息展示 -->
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
        <el-card class="result-card" v-if="result">
          <template #header>
            <div class="result-header">
              <h3>
                <el-icon><DocumentCopy /></el-icon>
                查询结果
              </h3>
              <div class="result-meta">
                <span class="meta-item">
                  <el-icon><Timer /></el-icon>
                  {{ result.execution_time_ms }}ms
                </span>
                <span class="meta-item">
                  共 {{ result.total }} 条
                </span>
                <el-tag v-if="result.cache_hit" type="success" size="small">缓存命中</el-tag>
                <el-tag v-if="result.suggest_async" type="warning" size="small">建议异步导出</el-tag>
              </div>
            </div>
          </template>

          <EnhancedTable
            :data="tableData"
            :columns="result.columns"
            :loading="false"
            table-id="query-editor-result"
            show-toolbar
            searchable
            fixable
            summarizable
          />

          <div class="result-footer">
            <el-pagination
              background
              layout="prev, pager, next, sizes, total"
              :total="result.total"
              :page-size="pageSize"
              :page-sizes="[20, 50, 100, 200]"
              :current-page="currentPage"
              @current-change="handlePageChange"
              @update:page-size="handlePageSizeChange"
            />
          </div>
        </el-card>

        <div v-else class="empty-result">
          <el-empty description="执行查询后结果将显示在这里" />
        </div>

        <!-- SQL 复杂度分析 -->
        <SQLAnalysisPanel :sql="queryForm.sql" />
      </div>
    </div>

    <!-- 查询历史抽屉 -->
    <el-drawer
      v-model="historyDrawerVisible"
      title="查询历史"
      size="350px"
      direction="ltr"
    >
      <div class="history-list">
        <div
          v-for="(item, index) in queryHistory"
          :key="index"
          class="history-item"
          @click="selectHistory(item)"
        >
          <div class="history-sql">{{ item.sql?.substring(0, 120) }}{{ item.sql?.length > 120 ? '...' : '' }}</div>
          <div class="history-meta">
            <span class="history-ds">{{ item.data_source_name || '数据源#' + item.data_source_id }}</span>
            <span class="history-time">{{ formatTime(item.created_at) }}</span>
          </div>
        </div>
        <div v-if="queryHistory.length === 0" class="history-empty">
          <el-empty description="暂无查询历史" :image-size="60" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, Download, DocumentCopy, Connection, Warning, Timer } from '@element-plus/icons-vue'
import { getDataSourceList } from '@/api/data_source'
import { executeSQL, getQueryHistory } from '@/api/query'
import { exportExcel, exportPDF } from '@/api/report'
import EnhancedTable from '@/components/EnhancedTable.vue'
import SQLAnalysisPanel from '@/components/SQLAnalysisPanel.vue'
import DialectSelector from '@/components/DialectSelector.vue'
import { useFormPersistence } from '@/composables/useFormPersistence'

export default {
  name: 'QueryEditor',
  components: { EnhancedTable, SQLAnalysisPanel, DialectSelector },
  setup() {
    const loading = ref(false)
    const dataSources = ref([])
    const result = ref(null)
    const errorMessage = ref('')
    const sqlInputRef = ref(null)

    // ---- 表单持久化 ----
    const { loadStored, saveToStorage } = useFormPersistence('query_editor_form', {
      data_source_id: null,
      sql: '',
      dialect: ''
    })
    const queryForm = ref(loadStored())
    const saveForm = () => saveToStorage(queryForm.value)
    watch(queryForm, saveForm, { deep: true })

    // ---- 索引数组 → 对象数组 ----
    const tableData = computed(() => {
      if (!result.value || !result.value.rows || !result.value.columns) return []
      return result.value.rows.map(row => {
        const obj = {}
        result.value.columns.forEach((col, i) => {
          obj[col] = row[i]
        })
        return obj
      })
    })

    // ---- 分页 ----
    const currentPage = ref(1)
    const pageSize = ref(50)

    const reExecute = (page, pageSizeVal) => {
      currentPage.value = page
      pageSize.value = pageSizeVal
      doExecute(page, pageSizeVal)
    }

    const handlePageChange = (page) => {
      reExecute(page, pageSize.value)
    }

    const handlePageSizeChange = (val) => {
      pageSize.value = val
      currentPage.value = 1
      reExecute(1, val)
    }

    // ---- 实际执行 ----
    const doExecute = async (page, pageSizeVal) => {
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
        // 替换参数占位符
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
          page: page || 1,
          page_size: pageSizeVal || pageSize.value
        }

        // 如果选择了方言，传递给后端
        if (queryForm.value.dialect) {
          payload.dialect = queryForm.value.dialect
        }

        result.value = await executeSQL(payload)
        currentPage.value = result.value.page || page || 1
        pageSize.value = result.value.page_size || pageSizeVal || 50
        ElMessage.success('查询成功')
      } catch (error) {
        const msg = error.response?.data?.detail || error.response?.data?.message || error.message || '查询失败'
        errorMessage.value = msg
        ElMessage.error(msg)
        result.value = null
      } finally {
        loading.value = false
      }
    }

    // 从表单直接执行
    const handleExecute = () => {
      doExecute(1, pageSize.value)
    }

    // ---- 参数化查询 ----
    const paramValues = ref({})

    function extractParams(sql) {
      const params = []
      const regex = /\$\{(\w+)\}/g
      let match
      while ((match = regex.exec(sql)) !== null) {
        if (!params.includes(match[1])) params.push(match[1])
      }
      return params
    }

    const extractedParams = ref([])

    watch(() => queryForm.value.sql, (sql) => {
      const params = extractParams(sql || '')
      extractedParams.value = params
      // 初始化新参数，保留旧值
      const newValues = { ...paramValues.value }
      params.forEach(p => {
        if (!(p in newValues)) newValues[p] = ''
      })
      // 清除不再存在的参数
      Object.keys(newValues).forEach(k => {
        if (!params.includes(k)) delete newValues[k]
      })
      paramValues.value = newValues
    })

    // ---- 数据源加载 ----
    const loadDataSources = async () => {
      try {
        dataSources.value = await getDataSourceList()
      } catch (error) {
        ElMessage.error('加载数据源失败')
      }
    }

    // ---- 查询历史 ----
    const historyDrawerVisible = ref(false)
    const queryHistory = ref([])

    const loadQueryHistory = async () => {
      try {
        const res = await getQueryHistory({ page: 1, page_size: 20 })
        queryHistory.value = Array.isArray(res) ? res : (res.items || res.records || res.data || [])
      } catch (error) {
        // 静默失败，不阻塞用户
        console.warn('加载查询历史失败', error)
      }
    }

    const selectHistory = (item) => {
      queryForm.value.data_source_id = item.data_source_id
      queryForm.value.sql = item.sql
      historyDrawerVisible.value = false
      // 如果历史有分页信息，自动重新执行
      ElMessage.info('已填入历史查询，请点击执行查询按钮')
    }

    function formatTime(timeStr) {
      if (!timeStr) return ''
      try {
        const d = new Date(timeStr)
        const pad = n => String(n).padStart(2, '0')
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
      } catch {
        return timeStr
      }
    }

    // ---- 导出 ----
    const exportingExcel = ref(false)
    const exportingPDF = ref(false)

    const handleExportExcel = async () => {
      if (!result.value) {
        ElMessage.warning('暂无查询结果')
        return
      }
      exportingExcel.value = true
      try {
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
        ElMessage.success('Excel 导出成功')
      } catch (error) {
        ElMessage.error('Excel 导出失败：' + (error.response?.data?.detail || error.message || '未知错误'))
      } finally {
        exportingExcel.value = false
      }
    }

    const handleExportPDF = async () => {
      if (!result.value) {
        ElMessage.warning('暂无查询结果')
        return
      }
      exportingPDF.value = true
      try {
        const response = await exportPDF({
          data_source_id: queryForm.value.data_source_id,
          sql: queryForm.value.sql,
          filename: `query_export_${Date.now()}.pdf`
        })
        const blob = new Blob([response], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `query_export_${Date.now()}.pdf`
        a.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('PDF 导出成功')
      } catch (error) {
        ElMessage.error('PDF 导出失败：' + (error.response?.data?.detail || error.message || '未知错误'))
      } finally {
        exportingPDF.value = false
      }
    }

    // ---- 快捷键 Ctrl+Enter ----
    const handleKeydown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleExecute()
      }
    }

    onMounted(() => {
      loadDataSources()
      loadQueryHistory()
      window.addEventListener('keydown', handleKeydown)
    })

    onBeforeUnmount(() => {
      window.removeEventListener('keydown', handleKeydown)
    })

    return {
      Clock,
      Download,
      DocumentCopy,
      Connection,
      Warning,
      Timer,
      loading,
      dataSources,
      queryForm,
      result,
      errorMessage,
      sqlInputRef,
      tableData,
      currentPage,
      pageSize,
      handleExecute,
      handlePageChange,
      handlePageSizeChange,
      handleExportExcel,
      handleExportPDF,
      // 参数化查询
      extractedParams,
      paramValues,
      // 查询历史
      historyDrawerVisible,
      queryHistory,
      formatTime,
      selectHistory,
    }
  }
}
</script>

<style scoped>
.query-editor-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.sidebar-toggle {
  margin-bottom: 12px;
}

.editor-layout {
  display: flex;
  gap: 16px;
}

.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.editor-card,
.result-card {
  width: 100%;
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.editor-header h3,
.result-header h3 {
  margin: 0;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-tags {
  display: flex;
  gap: 6px;
}

.editor-card :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #606266;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.result-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.empty-result {
  padding: 60px 0;
}

.error-alert {
  margin-bottom: 0;
}

/* ---- 查询历史抽屉 ---- */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.history-item:hover {
  background: #f5f7fa;
  border-color: #409eff;
}

.history-sql {
  font-family: monospace;
  font-size: 13px;
  color: #303133;
  line-height: 1.4;
  margin-bottom: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}

.history-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

.history-ds {
  color: #409eff;
}

.history-empty {
  padding: 40px 0;
}
</style>
