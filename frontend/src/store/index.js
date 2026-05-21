import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { getMenuTree } from "@/api/menu"

/**
 * ⚠️ 安全说明：当前使用 sessionStorage 存储 Token。
 *
 * sessionStorage 在关闭标签页后自动清除，比 localStorage 更安全。
 * 但 Token 仍可被 JavaScript 读取，存在 XSS 窃取风险。
 * 生产环境建议迁移至 httpOnly Cookie（后端设置，前端无法读取）。
 *
 * 迁移方案参考：后端设置 Cookie（httpOnly, Secure, SameSite=Strict），
 * 前端移除所有 Token 读写逻辑，改为依赖 Cookie 自动携带。
 */

const STORAGE = window.sessionStorage

export const useUserStore = defineStore("user", () => {
  const token = ref(STORAGE.getItem("token") || "")
  const user = ref(JSON.parse(STORAGE.getItem("user") || "null"))

  // 角色相关
  const role = computed(() => user.value?.role || "user")
  const isAdmin = computed(() => role.value === "admin")
  const isEditor = computed(() => role.value === "editor" || role.value === "admin")

  function setToken(newToken) {
    token.value = newToken
    STORAGE.setItem("token", newToken)
  }

  function setUser(newUser) {
    // 将 role_id (数字) 转换为角色名称 (字符串)
    const roleMap = { 1: 'admin', 2: 'editor', 3: 'user' }
    const userWithRole = {
      ...newUser,
      role: roleMap[newUser.role_id] || 'user'
    }
    user.value = userWithRole
    STORAGE.setItem("user", JSON.stringify(userWithRole))
  }

  function logout() {
    token.value = ""
    user.value = null
    STORAGE.removeItem("token")
    STORAGE.removeItem("user")
    // 清空菜单缓存
    const menuStore = useMenuStore()
    menuStore.clearMenus()
  }

  // 检查是否有指定角色
  function hasRole(requiredRoles) {
    if (!Array.isArray(requiredRoles)) {
      requiredRoles = [requiredRoles]
    }
    return requiredRoles.includes(role.value)
  }

  return { 
    token, 
    user, 
    role,
    isAdmin,
    isEditor,
    setToken, 
    setUser, 
    logout,
    hasRole
  }
})

export const useMenuStore = defineStore("menu", () => {
  const menus = ref([])
  const loaded = ref(false)
  const loading = ref(false)

  // 过滤启用的菜单
  function filterEnabledMenus(menuList) {
    return menuList
      .filter(m => m.is_enabled && m.is_visible)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .map(m => {
        if (m.children && m.children.length > 0) {
          return {
            ...m,
            children: filterEnabledMenus(m.children)
          }
        }
        return m
      })
  }

  // 加载菜单（只加载一次）
  async function loadMenus(force = false) {
    if (loaded.value && !force) {
      return menus.value
    }
    if (loading.value) {
      return menus.value
    }
    
    loading.value = true
    try {
      const res = await getMenuTree()
      // 响应拦截器已提取 data，res 直接是数组
      const menuList = Array.isArray(res) ? res : (res.data || [])
      menus.value = filterEnabledMenus(menuList)
      loaded.value = true
      return menus.value
    } catch (error) {
      // 静默失败，菜单加载失败不影响页面基本功能
      return []
    } finally {
      loading.value = false
    }
  }

  // 清空菜单（登出时调用）
  function clearMenus() {
    menus.value = []
    loaded.value = false
  }

  // 刷新菜单（菜单管理页面修改后调用）
  async function refreshMenus() {
    loaded.value = false
    return loadMenus(true)
  }

  return {
    menus,
    loaded,
    loading,
    loadMenus,
    clearMenus,
    refreshMenus
  }
})