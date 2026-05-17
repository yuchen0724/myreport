import { ref, watch } from "vue"

const STORAGE_PREFIX = "report_layout_"

/**
 * 布局布局持久化 composable
 * @param {string} layoutId - 布局 ID
 */
export function useLayoutStorage(layoutId) {
  const layoutItems = ref([])
  const isEditing = ref(false)
  const layoutName = ref("新建布局")

  // 从 localStorage 恢复
  const loadFromStorage = () => {
    const key = STORAGE_PREFIX + layoutId
    const saved = localStorage.getItem(key)
    if (saved) {
      try {
        const data = JSON.parse(saved)
        layoutName.value = data.name || "新建布局"
        layoutItems.value = data.items || []
      } catch { /* ignore */ }
    }
  }

  // 保存到 localStorage
  const saveToStorage = () => {
    const key = STORAGE_PREFIX + layoutId
    localStorage.setItem(
      key,
      JSON.stringify({ name: layoutName.value, items: layoutItems.value })
    )
  }

  // items 变化时自动保存
  watch(layoutItems, saveToStorage, { deep: true })

  // 重置布局
  const resetLayout = (preset = "default") => {
    const presets = {
      default: [
        { widget_type: "stat", widget_subtype: "data_source_count", title: "数据源", grid_x: 0, grid_y: 0, grid_w: 3, grid_h: 1 },
        { widget_type: "stat", widget_subtype: "query_count", title: "查询次数", grid_x: 3, grid_y: 0, grid_w: 3, grid_h: 1 },
        { widget_type: "stat", widget_subtype: "export_count", title: "导出次数", grid_x: 6, grid_y: 0, grid_w: 3, grid_h: 1 },
        { widget_type: "stat", widget_subtype: "template_count", title: "模板数量", grid_x: 9, grid_y: 0, grid_w: 3, grid_h: 1 },
        { widget_type: "chart", widget_subtype: "line", title: "趋势图", grid_x: 0, grid_y: 1, grid_w: 6, grid_h: 4 },
        { widget_type: "chart", widget_subtype: "bar", title: "柱状图", grid_x: 6, grid_y: 1, grid_w: 6, grid_h: 4 },
      ],
      analysis: [
        { widget_type: "nl2sql", title: "智能查询", grid_x: 0, grid_y: 0, grid_w: 4, grid_h: 6 },
        { widget_type: "chart", widget_subtype: "bar", title: "图表分析", grid_x: 4, grid_y: 0, grid_w: 4, grid_h: 3 },
        { widget_type: "chart", widget_subtype: "pie", title: "占比分析", grid_x: 8, grid_y: 0, grid_w: 4, grid_h: 3 },
        { widget_type: "table", title: "数据表格", grid_x: 4, grid_y: 3, grid_w: 8, grid_h: 3 },
      ],
      monitor: [
        { widget_type: "stat", widget_subtype: "data_source_count", title: "数据源", grid_x: 0, grid_y: 0, grid_w: 2, grid_h: 1 },
        { widget_type: "stat", widget_subtype: "query_count", title: "查询次数", grid_x: 2, grid_y: 0, grid_w: 2, grid_h: 1 },
        { widget_type: "stat", widget_subtype: "export_count", title: "导出次数", grid_x: 4, grid_y: 0, grid_w: 2, grid_h: 1 },
        { widget_type: "stat", widget_subtype: "template_count", title: "模板数量", grid_x: 6, grid_y: 0, grid_w: 2, grid_h: 1 },
        { widget_type: "chart", widget_subtype: "gauge", title: "核心指标", grid_x: 8, grid_y: 0, grid_w: 4, grid_h: 2 },
        { widget_type: "chart", widget_subtype: "line", title: "实时趋势", grid_x: 0, grid_y: 1, grid_w: 12, grid_h: 3 },
      ],
      blank: [],
    }
    layoutItems.value = presets[preset] || presets.default
  }

  return {
    layoutItems,
    isEditing,
    layoutName,
    loadFromStorage,
    saveToStorage,
    resetLayout,
  }
}
