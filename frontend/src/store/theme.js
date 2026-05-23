import { defineStore } from "pinia"
import { ref, computed, watch, onMounted } from "vue"

export const useThemeStore = defineStore("theme", () => {
  const STORAGE_KEY = "myreport-theme"

  const theme = ref(localStorage.getItem(STORAGE_KEY) || "system")

  // 检测系统偏好
  const systemDark = ref(false)
  let mediaQuery = null

  function detectSystem() {
    mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
    systemDark.value = mediaQuery.matches
    mediaQuery.addEventListener("change", (e) => {
      systemDark.value = e.matches
    })
  }

  onMounted(() => {
    detectSystem()
  })

  const isDark = computed(() => {
    if (theme.value === "system") return systemDark.value
    return theme.value === "dark"
  })

  // 监听主题变化，更新 DOM
  watch(isDark, (dark) => {
    if (dark) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, { immediate: true })

  function setTheme(t) {
    theme.value = t
    localStorage.setItem(STORAGE_KEY, t)
    // 立即应用
    const dark = isDark.value
    if (dark) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }

  function toggleTheme() {
    setTheme(isDark.value ? "light" : "dark")
  }

  return {
    theme,
    isDark,
    setTheme,
    toggleTheme,
  }
})
