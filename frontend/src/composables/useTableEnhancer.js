// frontend/src/composables/useTableEnhancer.js
// 通用表格增强组合式函数 — 列显隐/拖拽/固定/汇总/行展开/搜索/列宽持久化
// 支持两种模式：
//   mode='dynamic' (默认): 动态列，支持列拖拽排序、列固定
//   mode='static': 固定列列表页，支持列显隐、搜索、列宽持久化

import { ref, computed, watch, nextTick } from 'vue'
import { useTableStorage } from './useTableStorage'

export function useTableEnhancer(opts = {}) {
  const {
    mode = 'dynamic',               // 'dynamic' | 'static'
    tableId = 'default',            // localStorage key 后缀
    columns = ref([]),              // 动态列名数组 (dynamic mode)
    enableColumnDrag = true,        // 列拖拽排序 (仅 dynamic mode)
    enableColumnFix = true,         // 列固定 (仅 dynamic mode)
    enableSummary = true,           // 汇总行 (仅 dynamic mode)
    enableExpand = true,            // 行展开
    enableSearch = true,            // 搜索过滤
    expandThreshold = 6,            // 超过此列数自动启用行展开
  } = opts

  const storage = useTableStorage(tableId)

  // ---- 列显隐 ----
  const visibleColumns = ref([])
  const showExpand = ref(false)

  // ---- 搜索 ----
  const searchText = ref('')

  // ---- 引用 ----
  const tableRef = ref(null)

  // ---- 初始化列 (dynamic mode) ----
  if (mode === 'dynamic') {
    watch(columns, (cols) => {
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
  }

  // ---- 列拖拽排序 (dynamic mode + SortableJS) ----
  let columnDragInitialized = false
  let sortableInstance = null

  function initColumnDrag() {
    if (mode !== 'dynamic' || !enableColumnDrag) return
    if (!tableRef.value || columnDragInitialized) return
    const el = tableRef.value?.$el?.querySelector('.el-table__header-wrapper .el-table__header tr')
    if (!el) return

    import('sortablejs').then((Sortable) => {
      sortableInstance = Sortable.default.create(el, {
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
      columnDragInitialized = true
    }).catch(() => {
      // sortablejs 不可用时静默降级
    })
  }

  // ---- 列宽拖拽持久化 ----
  function handleHeaderDragEnd(newWidth, oldWidth, column) {
    if (column && column.property) {
      storage.saveColumnWidth(column.property, newWidth)
    }
  }

  // ---- 列固定 (dynamic mode) ----
  function handleColumnAction(cmd, col) {
    if (cmd === 'fixed-left') {
      storage.saveFixedColumn(col, 'left')
    } else if (cmd === 'fixed-right') {
      storage.saveFixedColumn(col, 'right')
    } else if (cmd === 'clear-fixed') {
      storage.saveFixedColumn(col, false)
    } else if (cmd.startsWith('summary-') && enableSummary) {
      const type = cmd.replace('summary-', '')
      const sc = storage.loadSummaryConfig() || {}
      storage.saveSummaryConfig({ ...sc, [col]: type })
    } else if (cmd === 'clear-summary' && enableSummary) {
      const sc = storage.loadSummaryConfig() || {}
      if (sc[col]) { delete sc[col]; storage.saveSummaryConfig(sc) }
    }
    // 触发响应式刷新
    visibleColumns.value = [...visibleColumns.value]
  }

  // ---- 汇总行 (dynamic mode) ----
  function handleSummary({ columns: cols, data: rows }) {
    if (!enableSummary) return []
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

  // ---- 行展开 ----
  function toggleExpand() {
    showExpand.value = !showExpand.value
  }

  // ---- 列固定状态辅助 (for dropdown disabled) ----
  function isFixedLeft(col) {
    return storage.loadFixedColumn(col) === 'left'
  }
  function isFixedRight(col) {
    return storage.loadFixedColumn(col) === 'right'
  }
  function isAnyFixed(col) {
    return !!storage.loadFixedColumn(col)
  }

  // ---- 搜索过滤 (对 data 进行过滤的函数) ----
  function applySearch(data) {
    if (!enableSearch || !searchText.value) return data
    const q = searchText.value.toLowerCase()
    return data.filter(row => {
      return Object.values(row).some(v => {
        if (v === null || v === undefined) return false
        return String(v).toLowerCase().includes(q)
      })
    })
  }

  // 清理
  function destroy() {
    if (sortableInstance) {
      sortableInstance.destroy()
      sortableInstance = null
    }
    columnDragInitialized = false
  }

  return {
    // 状态
    visibleColumns,
    showExpand,
    searchText,
    tableRef,

    // 存储
    storage,
    columns: mode === 'dynamic' ? columns : undefined,

    // 方法
    initColumnDrag,
    handleHeaderDragEnd,
    handleColumnAction,
    handleSummary,
    toggleExpand,
    applySearch,
    isFixedLeft,
    isFixedRight,
    isAnyFixed,
    destroy,
  }
}
