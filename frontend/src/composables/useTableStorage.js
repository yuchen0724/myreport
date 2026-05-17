// frontend/src/composables/useTableStorage.js
// 通用表格配置持久化 composable
// 使用 localStorage 存储，key 格式为 `table_config:${tableId}`

const STORAGE_PREFIX = 'table_config'

export function useTableStorage(tableId) {
  const storageKey = `${STORAGE_PREFIX}:${tableId}`

  function getConfig() {
    try {
      const raw = localStorage.getItem(storageKey)
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  }

  function saveConfig(config) {
    try {
      const existing = getConfig()
      const merged = { ...existing, ...config }
      localStorage.setItem(storageKey, JSON.stringify(merged))
    } catch (e) {
      console.warn('useTableStorage: 保存配置失败', e)
    }
  }

  // 列顺序
  function saveColumnOrder(keys) {
    saveConfig({ columnOrder: keys })
  }
  function loadColumnOrder() {
    return getConfig().columnOrder || null
  }

  // 列宽：{ [columnKey]: width }
  function saveColumnWidth(key, width) {
    const existing = getConfig()
    const columnWidths = existing.columnWidths || {}
    columnWidths[key] = width
    saveConfig({ columnWidths })
  }
  function loadColumnWidth(key) {
    const config = getConfig()
    return config.columnWidths?.[key] || null
  }

  // 固定列：{ [columnKey]: 'left'|'right'|false }
  function saveFixedColumn(key, direction) {
    const existing = getConfig()
    const fixedColumns = existing.fixedColumns || {}
    if (direction) {
      fixedColumns[key] = direction
    } else {
      delete fixedColumns[key]
    }
    saveConfig({ fixedColumns })
  }
  function loadFixedColumn(key) {
    const config = getConfig()
    return config.fixedColumns?.[key] || false
  }

  // 汇总配置：{ [columnKey]: { type: 'sum'|'avg'|'min'|'max'|'count' } }
  function saveSummaryConfig(cols) {
    saveConfig({ summaryColumns: cols })
  }
  function loadSummaryConfig() {
    return getConfig().summaryColumns || null
  }

  // 清除该 tableId 的所有配置
  function clearAll() {
    localStorage.removeItem(storageKey)
  }

  return {
    saveColumnOrder,
    loadColumnOrder,
    saveColumnWidth,
    loadColumnWidth,
    saveFixedColumn,
    loadFixedColumn,
    saveSummaryConfig,
    loadSummaryConfig,
    clearAll,
  }
}
