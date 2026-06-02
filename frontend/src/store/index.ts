import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { getMenuTree } from "@/api/menu"

export interface UserInfo {
  id: number
  username: string
  email: string
  role_id: number
  role?: string
}

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

/**
 * ⚠️ Security note: Token stored in sessionStorage.
 * sessionStorage is cleared on tab close — more secure than localStorage.
 * For production, consider httpOnly cookies (set by backend, invisible to JS).
 */

const STORAGE = window.sessionStorage

// ── Migrate legacy localStorage → sessionStorage ────────
if (!STORAGE.getItem("token") && window.localStorage.getItem("token")) {
  STORAGE.setItem("token", window.localStorage.getItem("token")!)
  STORAGE.setItem("user", window.localStorage.getItem("user") || "")
  window.localStorage.removeItem("token")
  window.localStorage.removeItem("user")
}

export const useUserStore = defineStore("user", () => {
  const token = ref<string>(STORAGE.getItem("token") || "")
  const user = ref<UserInfo | null>(JSON.parse(STORAGE.getItem("user") || "null"))

  const role = computed(() => user.value?.role || "user")
  const isAdmin = computed(() => role.value === "admin")
  const isEditor = computed(() => role.value === "editor" || role.value === "admin")

  function setToken(newToken: string) {
    token.value = newToken
    STORAGE.setItem("token", newToken)
  }

  function setUser(newUser: Partial<UserInfo>) {
    const roleMap: Record<number, string> = { 1: "admin", 2: "editor", 3: "user" }
    const userWithRole = {
      ...newUser,
      role: roleMap[newUser.role_id ?? 3] || "user",
    } as UserInfo
    user.value = userWithRole
    STORAGE.setItem("user", JSON.stringify(userWithRole))
  }

  function logout() {
    token.value = ""
    user.value = null
    STORAGE.removeItem("token")
    STORAGE.removeItem("user")
    const menuStore = useMenuStore()
    menuStore.clearMenus()
  }

  function hasRole(requiredRoles: string | string[]): boolean {
    if (!Array.isArray(requiredRoles)) {
      requiredRoles = [requiredRoles]
    }
    return requiredRoles.includes(role.value)
  }

  return { token, user, role, isAdmin, isEditor, setToken, setUser, logout, hasRole }
})

export const useMenuStore = defineStore("menu", () => {
  const menus = ref<MenuItem[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  function filterEnabledMenus(menuList: MenuItem[]): MenuItem[] {
    return menuList
      .filter(m => m.is_enabled && m.is_visible)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .map(m => ({
        ...m,
        children: m.children?.length ? filterEnabledMenus(m.children) : m.children,
      }))
  }

  async function loadMenus(force = false): Promise<MenuItem[]> {
    if (loaded.value && !force) return menus.value
    if (loading.value) return menus.value

    loading.value = true
    try {
      const res = await getMenuTree()
      const menuList = Array.isArray(res) ? res : ((res as Record<string, unknown>).data as MenuItem[] || [])
      menus.value = filterEnabledMenus(menuList)
      loaded.value = true
      return menus.value
    } catch {
      // 即使失败也标记已加载，避免每次导航都重试
      loaded.value = true
      return []
    } finally {
      loading.value = false
    }
  }

  function clearMenus() {
    menus.value = []
    loaded.value = false
  }

  async function refreshMenus(): Promise<MenuItem[]> {
    loaded.value = false
    return loadMenus(true)
  }

  return { menus, loaded, loading, loadMenus, clearMenus, refreshMenus }
})
