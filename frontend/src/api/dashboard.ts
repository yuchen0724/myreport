import request from "@/utils/request"

export interface DashboardLayout {
  id: number
  name: string
  description?: string
  created_by: number
  created_at: string
}

export interface WidgetConfig {
  id: number
  layout_id: number
  type: string
  title: string
  config: Record<string, unknown>
  x: number
  y: number
  w: number
  h: number
}

// ==================== Layout API ====================

export function getLayoutList(): Promise<DashboardLayout[]> {
  return request({ url: "/dashboard/layouts", method: "get" }) as Promise<DashboardLayout[]>
}

export function getLayoutDetail(id: number): Promise<DashboardLayout> {
  return request({ url: `/dashboard/layouts/${id}`, method: "get" }) as Promise<DashboardLayout>
}

export function createLayout(data: { name: string; description?: string }): Promise<DashboardLayout> {
  return request({ url: "/dashboard/layouts", method: "post", data }) as Promise<DashboardLayout>
}

export function updateLayout(id: number, data: Partial<DashboardLayout>): Promise<DashboardLayout> {
  return request({ url: `/dashboard/layouts/${id}`, method: "put", data }) as Promise<DashboardLayout>
}

export function deleteLayout(id: number): Promise<void> {
  return request({ url: `/dashboard/layouts/${id}`, method: "delete" }) as Promise<void>
}

// ==================== Widget API ====================

export function getWidgetList(layoutId: number): Promise<WidgetConfig[]> {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets`, method: "get" }) as Promise<WidgetConfig[]>
}

export function createWidget(layoutId: number, data: Partial<WidgetConfig>): Promise<WidgetConfig> {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets`, method: "post", data }) as Promise<WidgetConfig>
}

export function updateWidget(layoutId: number, widgetId: number, data: Partial<WidgetConfig>): Promise<WidgetConfig> {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets/${widgetId}`, method: "put", data }) as Promise<WidgetConfig>
}

export function deleteWidget(layoutId: number, widgetId: number): Promise<void> {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets/${widgetId}`, method: "delete" }) as Promise<void>
}

export function saveWidgetBatch(layoutId: number, widgets: Partial<WidgetConfig>[]): Promise<void> {
  return request({ url: `/dashboard/layouts/${layoutId}/widgets`, method: "put", data: widgets }) as Promise<void>
}

// ==================== Legacy APIs ====================

export function getWidgetConfig(): Promise<WidgetConfig[]> {
  return request({ url: "/dashboard/widgets", method: "get" }) as Promise<WidgetConfig[]>
}

export function saveWidgetConfig(data: Record<string, unknown>): Promise<void> {
  return request({ url: "/dashboard/widgets", method: "put", data }) as Promise<void>
}

export function getDashboardData(): Promise<Record<string, unknown>> {
  return request({ url: "/dashboard/data", method: "get" }) as Promise<Record<string, unknown>>
}

// ==================== Drilldown API ====================

export function executeDrilldown(data: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request({ url: "/drilldown/execute", method: "post", data }) as Promise<Record<string, unknown>>
}

export function getDrilldownConfig(widgetId: number): Promise<Record<string, unknown>> {
  return request({ url: `/drilldown/config/${widgetId}`, method: "get" }) as Promise<Record<string, unknown>>
}
