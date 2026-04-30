import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { getMenuTree } from "@/api/menu"

export const useUserStore = defineStore("user", () => {
  const token = ref(localStorage.getItem("token") || "")
  const user = ref(JSON.parse(localStorage.getItem("user") || "null"))

  // 角色相关
  const role = computed(() => user.value?.role || "user")
  const isAdmin = computed(() => role.value === "admin")
  const isEditor = computed(() => role.value === "editor" || role.value === "admin")

  function setToken(newToken) {
    token.value = newToken
    localStorage.setItem("token", newToken)
  }

  function setUser(newUser) {
    user.value = newUser
    localStorage.setItem("user", JSON.stringify(newUser))
  }

  function logout() {
    token.value = ""
    user.value = null
    localStorage.removeItem("token")
    localStorage.removeItem("user")
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
      const menuList = res.data || []
      menus.value = filterEnabledMenus(menuList)
      loaded.value = true
      return menus.value
    } catch (error) {
      console.error('加载菜单失败:', error)
      // 如果是 401，静默失败
      if (error.response?.status !== 401) {
        // 其他错误也静默失败
      }
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