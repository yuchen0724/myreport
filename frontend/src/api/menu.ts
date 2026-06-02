import request from "@/utils/request"

export interface MenuItem {
  id: number
  name: string
  path: string
  icon?: string
  parent_id?: number
  sort_order: number
  is_enabled: boolean
  is_visible: boolean
  children?: MenuItem[]
}

export function getMenuTree(): Promise<MenuItem[]> {
  return request({ url: "/menus/tree", method: "get" }) as Promise<MenuItem[]>
}

export function createMenu(data: Partial<MenuItem>): Promise<MenuItem> {
  return request({ url: "/menus", method: "post", data }) as Promise<MenuItem>
}

export function updateMenu(id: number, data: Partial<MenuItem>): Promise<MenuItem> {
  return request({ url: `/menus/${id}`, method: "put", data }) as Promise<MenuItem>
}

export function deleteMenu(id: number): Promise<void> {
  return request({ url: `/menus/${id}`, method: "delete" }) as Promise<void>
}

// ── Legacy name aliases ───────────────────────────────────
export function getMenus(params?: Record<string, unknown>): Promise<MenuItem[]> {
  return request({ url: "/menus", method: "get", params }) as Promise<MenuItem[]>
}
export function getMenuWithTemplate(menuId: number): Promise<MenuItem & { template?: Record<string, unknown> }> {
  // 后端路由: GET /api/menus/template/{menu_id}
  return request({ url: `/menus/template/${menuId}`, method: "get" }) as Promise<MenuItem & { template?: Record<string, unknown> }>
}
