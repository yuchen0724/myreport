<template>
  <div class="query-result">
      <el-card>
        <template #header>
          <h3>查询结果</h3>
        </template>
      <div class="table-toolbar" v-if="visibleColumns.length > 0">
        <TableToolbar
          :all-columns="result.columns"
          v-model="visibleColumns"
          :enable-expand="result.columns.length > 6"
          :expanded="showExpand"
          @toggle-expand="toggleExpand"
        />
      </div>
      <el-table
        ref="tableRef"
        :data="tableData"
        v-loading="loading"
        border
        stripe
        @header-dragend="handleHeaderDragEnd"
        :show-summary="true"
        :summary-method="handleSummary"
        max-height="500"
        style="width: 100%"
      >
        <el-table-column type="expand" v-if="showExpand">
          <template #default="{ row }">
            <div class="expand-detail">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item
                  v-for="(val, key) in row"
                  :key="key"
                  :label="key"
                >
                  {{ val !== null && val !== undefined ? val : '-' }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          v-for="(col, index) in visibleColumns"
          :key="index"
          :prop="col"
          :label="col"
          :width="storage.loadColumnWidth(col) || undefined"
          :fixed="storage.loadFixedColumn(col) || false"
          min-width="80"
          show-overflow-tooltip
        >
          <template #header>
            <div class="column-header-with-actions">
              <span>{{ col }}</span>
              <el-dropdown trigger="click" size="small" @command="(cmd) => handleColumnAction(cmd, col)">
                <el-button size="small" circle :icon="MoreFilled" class="col-action-btn" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="fixed-left" :disabled="storage.loadFixedColumn(col) === 'left'">固定到左侧</el-dropdown-item>
                    <el-dropdown-item command="fixed-right" :disabled="storage.loadFixedColumn(col) === 'right'">固定到右侧</el-dropdown-item>
                    <el-dropdown-item command="clear-fixed" :disabled="!storage.loadFixedColumn(col)">取消固定</el-dropdown-item>
                    <el-dropdown-item divided command="summary-sum">汇总：求和</el-dropdown-item>
                    <el-dropdown-item command="summary-avg">汇总：平均数</el-dropdown-item>
                    <el-dropdown-item command="summary-min">汇总：最小值</el-dropdown-item>
                    <el-dropdown-item command="summary-max">汇总：最大值</el-dropdown-item>
                    <el-dropdown-item command="summary-count">汇总：计数</el-dropdown-item>
                    <el-dropdown-item divided command="clear-summary">清除汇总</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
        <div class="result-footer">
          <div class="result-info">执行时间: {{ result.execution_time_ms }}ms，共 {{ result.total }} 条记录</div>
          <el-pagination
            background
            layout="prev, pager, next, sizes, total"
            :total="result.total"
            :page-size="pageSize"
            :page-sizes="[20, 50, 100, 200]"
            :current-page="currentPage"
            @current-change="handlePageChange"
            @update:page-size="(val) => { pageSize = val; currentPage = 1 }"
          />
        </div>
        <div class="export-buttons">
          <el-button @click="handleExportExcel" :loading="exportingExcel">导出 Excel</el-button>
          <el-button @click="handleExportPDF" :loading="exportingPDF">导出 PDF</el-button>
        </div>
      </el-card>
    </div></template>

<script>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { MoreFilled } from '@element-plus/icons-vue'
import { exportExcel, exportPDF } from '@/api/report'
import TableToolbar from '@/components/TableToolbar.vue'
import { useTableStorage } from '@/composables/useTableStorage'

export default {
  name: 'QueryResult',
  components: { TableToolbar },
  props: {
    dataSourceId: {
      type: Number,
      default: null
    },
    querySql: {
      type: String,
      default: ''
    },
    result: {
      type: Object,
      default: () => ({ columns: [], rows: [], total: 0, page: 1, page_size: 50, execution_time_ms: 0 })
    }
  },
  emits: ['re-query'],
  setup(props, { emit }) {
    const loading = ref(false)
    const exportingExcel = ref(false)
    const exportingPDF = ref(false)
    const currentPage = ref(1)
    const pageSize = ref(50)

    // 表格增强
    const visibleColumns = ref([])
    const showExpand = ref(false)
    const tableRef = ref(null)

    const storage = useTableStorage(`query:${props.dataSourceId || 'default'}`)

    // 将数字索引 rows 转为对象数组
    const tableData = computed(() => {
      const cols = props.result?.columns || []
      const rows = props.result?.rows || []
      return rows.map(row => {
        const obj = {}
        cols.forEach((col, i) => { obj[col] = row[i] })
        return obj
      })
    })

    // 数据列变化时初始化可见列 + 恢复持久化列顺序
    watch(() => props.result?.columns, (cols) => {
      if (!cols || cols.length === 0) return
      const saved = storage.loadColumnOrder()
      if (saved && saved.length > 0) {
        const valid = saved.filter(c => cols.includes(c))
        if (valid.length > 0) {
          visibleColumns.value = valid
          return
        }
      }
      visibleColumns.value = [...cols]
      nextTick(() => initColumnDrag())
    }, { immediate: true })

    const handlePageChange = (page) => {
      currentPage.value = page
      emit('re-query', { page, page_size: pageSize.value })
    }

    const handleExportExcel = async () => {
      if (!props.result?.rows?.length) {
        ElMessage.warning('没有查询结果可导出')
        return
      }
      exportingExcel.value = true
      try {
        const response = await exportExcel({
          data_source_id: props.dataSourceId,
          sql: props.querySql,
          filename: `report_${Date.now()}.xlsx`
        })
        const blob = new Blob([response], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `report_${Date.now()}.xlsx`; a.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('Excel 导出成功')
      } catch (error) {
        ElMessage.error('Excel 导出失败：' + (error.message || '未知错误'))
      } finally {
        exportingExcel.value = false
      }
    }

    const handleExportPDF = async () => {
      if (!props.result?.rows?.length) {
        ElMessage.warning('没有查询结果可导出')
        return
      }
      exportingPDF.value = true
      try {
        const response = await exportPDF({
          data_source_id: props.dataSourceId,
          sql: props.querySql,
          filename: `report_${Date.now()}.pdf`
        })
        const blob = new Blob([response], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `report_${Date.now()}.pdf`; a.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('PDF 导出成功')
      } catch (error) {
        ElMessage.error('PDF 导出失败：' + (error.message || '未知错误'))
      } finally {
        exportingPDF.value = false
      }
    }

    // ---- 行展开 ----
    function toggleExpand() {
      showExpand.value = !showExpand.value
    }

    // ---- 列拖拽 ----
    function initColumnDrag() {
      if (!tableRef.value) return
      const el = tableRef.value?.$el?.querySelector('.el-table__header-wrapper .el-table__header tr')
      if (!el || el._sortableInitialized) return
      const Sortable = require('sortablejs')
      Sortable.create(el, {
        animation: 150,
        onEnd: (evt) => {
          if (evt.oldIndex === evt.newIndex) return
          const order = [...visibleColumns.value]
          const [moved] = order.splice(evt.oldIndex, 1)
          order.splice(evt.newIndex, 0, moved)
          visibleColumns.value = order
          storage.saveColumnOrder(order)
        }
      })
      el._sortableInitialized = true
    }

    // ---- 列宽拖动 ----
    function handleHeaderDragEnd(newWidth, oldWidth, column) {
      if (column && column.property) {
        storage.saveColumnWidth(column.property, newWidth)
      }
    }

    // ---- 固定列 + 汇总 ----
    function handleColumnAction(cmd, col) {
      switch (true) {
        case cmd === 'fixed-left':
          storage.saveFixedColumn(col, 'left'); break
        case cmd === 'fixed-right':
          storage.saveFixedColumn(col, 'right'); break
        case cmd === 'clear-fixed':
          storage.saveFixedColumn(col, false); break
        case cmd.startsWith('summary-'): {
          const type = cmd.replace('summary-', '')
          const sc = storage.loadSummaryConfig() || {}
          storage.saveSummaryConfig({ ...sc, [col]: type })
          break
        }
        case cmd === 'clear-summary': {
          const sc = storage.loadSummaryConfig() || {}
          if (sc[col]) { delete sc[col]; storage.saveSummaryConfig(sc) }
          break
        }
      }
      visibleColumns.value = [...visibleColumns.value]
    }

    // ---- 汇总行 ----
    function handleSummary({ columns: cols, data: rows }) {
      const config = storage.loadSummaryConfig()
      if (!config || Object.keys(config).length === 0) return []
      const labels = { sum: '合计', avg: '平均', min: '最小', max: '最大', count: '计数' }
      return cols.map(col => {
        const summary = config[col.property]
        if (!summary) return ''
        const vals = rows.map(r => Number(r[col.property])).filter(v => !isNaN(v))
        if (vals.length === 0) return ''
        let result
        switch (summary) {
          case 'sum': result = vals.reduce((a, b) => a + b, 0); break
          case 'avg': result = vals.reduce((a, b) => a + b, 0) / vals.length; break
          case 'min': result = Math.min(...vals); break
          case 'max': result = Math.max(...vals); break
          case 'count': result = vals.length; break
          default: return ''
        }
        return `${labels[summary]}: ${Number.isInteger(result) ? result : result.toFixed(2)}`
      })
    }

    return {
      loading,
      exportingExcel,
      exportingPDF,
      currentPage,
      pageSize,
      visibleColumns,
      showExpand,
      tableRef,
      tableData,
      handlePageChange,
      handleExportExcel,
      handleExportPDF,
      toggleExpand,
      storage,
      handleHeaderDragEnd,
      handleColumnAction,
      handleSummary,
    }
  }
}
</script>

<style scoped>
.query-result {
  padding: 20px;
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

.result-footer {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.result-info {
  color: #666;
}

.export-buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>