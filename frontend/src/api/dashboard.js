import request from "@/utils/request"

// ==================== 布局 API ====================

export function getLayoutList() {
  return request({ url: "/dashboard/layouts", method: "get" })
}

export function getLayoutDetail(id) {
  return request({ url: `/dashboard/layouts/${id}`, method: "get" })
}

export function createLayout(data) {
  return request({ url: "/dashboard/layouts", method: "post", data })
}

export function updateLayout(id, data) {
  return request({ url: `/dashboard/layouts/${id}`, method: "put", data })
}

export function deleteLayout(id) {
  return request({ url: `/dashboard/layouts/${id}`, method: "delete" })
}

// ==================== Widget API（基于布局） ====================

export function getWidgetList(layoutId) {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets`, method: "get" })
}

export function createWidget(layoutId, data) {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets`, method: "post", data })
}

export function updateWidget(layoutId, widgetId, data) {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets/${widgetId}`, method: "put", data })
}

export function deleteWidget(layoutId, widgetId) {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets/${widgetId}`, method: "delete" })
}

export function saveWidgetBatch(layoutId, widgets) {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets`, method: "put", data: widgets })
}

// ==================== 旧 API 兼容 ====================

export function getWidgetConfig() {
  return request({ url: "/dashboard/widgets", method: "get" })
}

export function saveWidgetConfig(data) {
  return request({ url: "/dashboard/widgets", method: "put", data })
}

export function getDashboardData() {
  return request({ url: "/dashboard/data", method: "get" })
}

// ==================== 钻取 API ====================

export function executeDrilldown(data) {
  return request({ url: "/drilldown/execute", method: "post", data })
}

export function getDrilldownConfig(widgetId) {
  return request({ url: `/drilldown/config/${widgetId}`, method: "get" })
}
