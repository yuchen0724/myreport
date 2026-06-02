import { defineStore } from "pinia"
import { ref, watch } from "vue"

export const useThemeStore = defineStore("theme", () => {
  const isDark = ref(document.documentElement.classList.contains("dark"))

  // Sync class on change
  watch(isDark, (val) => {
    if (val) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  })

  function toggleTheme() {
    isDark.value = !isDark.value
  }

  function setTheme(dark: boolean) {
    isDark.value = dark
  }

  return { isDark, toggleTheme, setTheme }
})
