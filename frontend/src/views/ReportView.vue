<template>
  <div class="report-view">
    <el-card v-loading="loading">
      
        <div class="card-header">
          <div class="title-section">
            <span class="title">{{ menuInfo?.name || '报表' }}</span>
            <el-tag v-if="templateInfo" type="info" size="small">
              {{ templateInfo.name }}
            </el-tag>
          </div>
          <div class="actions">
            <el-button @click="handleExport('excel')" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出 Excel
            </el-button>
            <el-button @click="handleExport('pdf')" :loading="exporting">
              <el-icon><Document /></el-icon>
              导出 PDF
            </el-button>
          </div>
        </div>
      

      <!-- 查询条件区域 -->
      <div v-if="templateInfo" class="params-section">
        <el-form :model="params" inline class="params-form">
          <el-form-item
            v-for="param in templateParams"
            :key="param.name"
            :label="param.label || param.name"
          >
            <el-input
              v-if="param.type === 'string'"
              v-model="params[param.name]"
              :placeholder="'请输入' + (param.label || param.name)"
              style="width: 200px"
            />
            <el-input-number
              v-else-if="param.type === 'number'"
              v-model="params[param.name]"
              :placeholder="'请输入' + (param.label || param.name)"
            />
            <el-date-picker
              v-else-if="param.type === 'date'"
              v-model="params[param.name]"
              type="date"
              :placeholder="'请选择' + (param.label || param.name)"
            />
            <el-date-picker
              v-else-if="param.type === 'daterange'"
              v-model="params[param.name]"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadData">
              <el-icon><Search /></el-icon>
              查询
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 数据表格工具栏 -->
      <div v-if="data.length > 0" class="table-toolbar">
        <TableToolbar
          :all-columns="columns"
          v-model="visibleColumns"
          v-model:search-text="searchText"
          :enable-expand="columns.length > 6"
          :expanded="showExpand"
          @toggle-expand="toggleExpand"
        />
      </div>

      <!-- 数据表格 -->
      <el-table
        v-if="data.length > 0"
        ref="tableRef"
        :data="paginatedData"
        border
        stripe
        :default-sort="{ prop: sortProp, order: sortOrder }"
        @sort-change="handleSortChange"
        @header-dragend="handleHeaderDragEnd"
        :show-summary="true"
        :summary-method="handleSummary"
        max-height="500"
        style="width: 100%"
      >
        <!-- 行展开列 -->
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
          v-for="col in visibleColumns"
          :key="col"
          :prop="col"
          :label="col"
          :width="storage.loadColumnWidth(col) || undefined"
          :fixed="storage.loadFixedColumn(col) || false"
          min-width="80"
          show-overflow-tooltip
          sortable="custom"
        >
          <!-- 列头操作：固定列 + 汇总 -->
          <template #header>
            <div class="column-header-with-actions">
              <span>{{ col }}</span>
              <el-dropdown trigger="click" size="small" @command="(cmd) => handleColumnAction(cmd, col)">
                <el-button size="small" circle :icon="MoreFilled" class="col-action-btn" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="fixed-left" :disabled="storage.loadFixedColumn(col) === 'left'">
                      固定到左侧
                    </el-dropdown-item>
                    <el-dropdown-item command="fixed-right" :disabled="storage.loadFixedColumn(col) === 'right'">
                      固定到右侧
                    </el-dropdown-item>
                    <el-dropdown-item command="clear-fixed" :disabled="!storage.loadFixedColumn(col)">
                      取消固定
                    </el-dropdown-item>
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

      <!-- 空状态 -->
      <el-empty v-else-if="!loading" description="暂无数据，请设置查询参数后点击查询" />

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @size-change="handlePageChange"
          @current-change="handlePageChange"
        />
        <span v-if="total > 100000" class="deep-page-tip">
          💡 提示：数据量较大时，建议使用"上一页/下一页"翻页
        </span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, Document, Search, Grid, MoreFilled } from '@element-plus/icons-vue'
import { getMenus, getMenuWithTemplate } from '@/api/menu'
import { executeQuery } from '@/api/query'
import { exportExcel, exportPDF } from '@/api/report'
import TableToolbar from '@/components/TableToolbar.vue'
import { useTableStorage } from '@/composables/useTableStorage'
import Sortable from 'sortablejs'

const route = useRoute()
const loading = ref(false)
const exporting = ref(false)
const menuInfo = ref(null)
const templateInfo = ref(null)
const data = ref([])
const columns = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const params = reactive({})
const templateParams = ref([])
const nextCursor = ref(null)

// 表格增强
const searchText = ref('')
const visibleColumns = ref([])
const sortProp = ref('')
const sortOrder = ref(null)
const showExpand = ref(false)
const tableRef = ref(null)

// tableId 按路由参数计算，支持持久化
const tableId = computed(() => `report:${route.params.id || 'default'}`)
const storage = useTableStorage(tableId.value)

function toggleExpand() {
  showExpand.value = !showExpand.value
}

// 初始化可见列 + 恢复持久化列顺序
watch(columns, (newCols) => {
  const savedOrder = storage.loadColumnOrder()
  if (savedOrder && savedOrder.length > 0) {
    const valid = savedOrder.filter(c => newCols.includes(c))
    if (valid.length > 0) {
      visibleColumns.value = valid
      return
    }
  }
  visibleColumns.value = [...newCols]
}, { immediate: true })

// 搜索筛���
const filteredData = computed(() => {
  if (!searchText.value) return data.value
  const keyword = searchText.value.toLowerCase()
  return data.value.filter(row =>
    Object.values(row).some(val => String(val).toLowerCase().includes(keyword))
  )
})

// 分页数据
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredData.value.slice(start, end)
})

// ---- 列拖拽 ----
function initColumnDrag() {
  if (!tableRef.value) return
  const el = tableRef.value.$el.querySelector('.el-table__header-wrapper .el-table__header tr')
  if (!el || el._sortableInitialized) return
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

// ---- 列宽拖动持久化 ----
function handleHeaderDragEnd(newWidth, oldWidth, column, event) {
  if (column && column.property) {
    storage.saveColumnWidth(column.property, newWidth)
  }
}

// ---- 固定列 + 汇总列操作 ----
function handleColumnAction(cmd, col) {
  switch (true) {
    case cmd === 'fixed-left':
      storage.saveFixedColumn(col, 'left')
      break
    case cmd === 'fixed-right':
      storage.saveFixedColumn(col, 'right')
      break
    case cmd === 'clear-fixed':
      storage.saveFixedColumn(col, false)
      break
    case cmd.startsWith('summary-'): {
      const type = cmd.replace('summary-', '')
      const sc = storage.loadSummaryConfig() || {}
      storage.saveSummaryConfig({ ...sc, [col]: type })
      break
    }
    case cmd === 'clear-summary': {
      const sc = storage.loadSummaryConfig() || {}
      if (sc[col]) {
        delete sc[col]
        storage.saveSummaryConfig(sc)
      }
      break
    }
  }
  visibleColumns.value = [...visibleColumns.value]
}

// ---- 汇总行计算 ----
function handleSummary({ columns: cols, data: rows }) {
  const config = storage.loadSummaryConfig()
  if (!config || Object.keys(config).length === 0) return []

  const labels = { sum: '合计', avg: '平均', min: '最小', max: '最大', count: '计数' }

  return cols.map(col => {
    const colKey = col.property
    const summary = config[colKey]
    if (!summary) return ''

    const vals = rows.map(r => Number(r[colKey])).filter(v => !isNaN(v))
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

// 排序处理
const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop
  sortOrder.value = order
  if (!prop || !order) return
  const mult = order === 'ascending' ? 1 : -1
  data.value.sort((a, b) => {
    const va = a[prop]; const vb = b[prop]
    if (va === vb) return 0
    if (va == null) return 1
    if (vb == null) return -1
    return typeof va === 'number' && typeof vb === 'number'
      ? (va - vb) * mult
      : String(va).localeCompare(String(vb)) * mult
  })
}

// 通过 path 查找菜单
const findMenuIdByPath = async (path) => {
  try {
    const menus = await getMenus({ skip: 0, limit: 1000 })
    const menuList = Array.isArray(menus) ? menus : (menus.data || [])
    const matched = menuList.find(m => m.path === path)
    return matched ? matched.id : null
  } catch { return null }
}

// 加载菜单和模板信息
const loadMenuInfo = async () => {
  let menuId = route.params.id
  if (!menuId) { ElMessage.error('缺少菜单ID'); return }
  try {
    loading.value = true
    if (!/^\d+$/.test(menuId)) {
      const resolvedId = await findMenuIdByPath('/report/' + menuId)
      if (resolvedId) { menuId = resolvedId }
      else { ElMessage.error('未找到对应菜单'); return }
    }
    const res = await getMenuWithTemplate(menuId)
    menuInfo.value = res
    templateInfo.value = res.template
    if (templateInfo.value?.config?.params) {
      templateParams.value = templateInfo.value.config.params
      templateParams.value.forEach(p => {
        if (p.default) params[p.name] = p.default
      })
    }
  } catch (error) {
    ElMessage.error('加载报表失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 构建带参数的 SQL
const buildSqlWithParams = () => {
  const config = templateInfo.value?.config
  if (!config?.sql) return ''
  let sql = config.sql
  Object.entries(params).forEach(([key, value]) => {
    let replaceValue = value
    if (value instanceof Date) {
      replaceValue = `${value.getFullYear()}${String(value.getMonth()+1).padStart(2,'0')}${String(value.getDate()).padStart(2,'0')}`
    } else if (Array.isArray(value) && value[0] instanceof Date) {
      replaceValue = value.map(d => `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`).join(',')
    }
    sql = sql.replace(new RegExp(`\\$\\{${key}\\}|:${key}`, 'g'), replaceValue ?? '')
  })
  return sql
}

// 加载数据
const loadData = async () => {
  if (!templateInfo.value) { ElMessage.warning('未关联报表模板'); return }
  const config = templateInfo.value.config
  if (!config) { ElMessage.error('模板缺少配置信息'); return }
  if (!config.data_source_id) { ElMessage.error('模板缺少数据源配置'); return }
  if (!config.sql) { ElMessage.error('模板缺少 SQL 配置'); return }

  try {
    loading.value = true
    const useCursor = currentPage.value > 1 && nextCursor.value
    const res = await executeQuery({
      data_source_id: config.data_source_id,
      sql: buildSqlWithParams(),
      params: {},
      page: useCursor ? 1 : currentPage.value,
      page_size: Math.min(pageSize.value, 5000),
      cursor: useCursor ? nextCursor.value : undefined,
    })
    const cols = res.columns || []
    const rawRows = res.rows || []
    data.value = rawRows.map(row => {
      const obj = {}
      cols.forEach((col, i) => { obj[col] = row[i] })
      return obj
    })
    columns.value = cols
    total.value = res.total || 0
    nextCursor.value = res.next_cursor || null

    // 数据加载完成后初始化列拖拽
    await nextTick()
    initColumnDrag()
  } catch (error) {
    ElMessage.error('查询失败：' + (error.response?.data?.detail || error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 分页变化
const handlePageChange = () => {
  if (currentPage.value === 1) nextCursor.value = null
  loadData()
}

// 导出
const handleExport = async (format) => {
  if (!templateInfo.value) { ElMessage.warning('未关联报表模板'); return }
  try {
    exporting.value = true
    const config = templateInfo.value.config
    const sql = buildSqlWithParams()
    const requestData = { data_source_id: config.data_source_id, sql }

    if (format === 'pdf') {
      const blob = await exportPDF(requestData)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${menuInfo.value.name || 'report'}.pdf`; a.click()
      window.URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
      return
    }

    const asyncFn = (await import('@/api/report')).exportExcelAsync
    const res = await asyncFn(requestData)
    const taskId = res?.task_id
    if (!taskId) { ElMessage.error('导出任务创建失败'); return }

    let taskStatus = 'pending'
    let maxAttempts = 60
    while (taskStatus === 'pending' || taskStatus === 'processing') {
      await new Promise(r => setTimeout(r, 2000))
      const statusRes = await import('@/api/report').then(m => m.getExportTask(taskId))
      taskStatus = statusRes?.status
      maxAttempts--
      if (maxAttempts <= 0) { ElMessage.warning('导出超时'); break }
    }

    if (taskStatus === 'completed') {
      const fileRes = await import('@/api/report').then(m => m.downloadExportFile(taskId))
      const blob = new Blob([fileRes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${menuInfo.value.name || 'report'}.xlsx`; a.click()
      window.URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    } else {
      ElMessage.error('导出失败，任务状态：' + taskStatus)
    }
  } catch (error) {
    ElMessage.error('导出失败：' + (error.response?.data?.detail || error.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}

// 监听路由变化
watch(() => route.params.id, (newId) => {
  if (newId) loadMenuInfo()
})

onMounted(() => {
  if (route.params.id) loadMenuInfo()
})
</script>

<style scoped>
.report-view { padding: 20px; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title { font-size: 18px; font-weight: 600; }
.params-section {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}
.params-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.pagination {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  justify-content: flex-end;
}
.deep-page-tip {
  color: #e6a23c;
  font-size: 12px;
}
.column-header-with-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.col-action-btn {
  opacity: 0.4;
  transition: opacity 0.2s;
}
.col-action-btn:hover {
  opacity: 1;
}
.expand-detail {
  padding: 12px;
}
</style>