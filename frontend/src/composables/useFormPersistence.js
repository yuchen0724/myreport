// frontend/src/composables/useFormPersistence.js
// 通用表单状态持久化 composable
// 自动同步 reactive/ref 到 localStorage，离开页面再回来保持上次输入

export function useFormPersistence(storageKey, defaultValues) {
  function loadStored() {
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const parsed = JSON.parse(saved)
        const result = {}
        for (const key of Object.keys(defaultValues)) {
          if (Object.prototype.hasOwnProperty.call(parsed, key)) {
            result[key] = parsed[key]
          } else {
            result[key] = defaultValues[key]
          }
        }
        return result
      }
    } catch { /* 忽略 */ }
    return { ...defaultValues }
  }

  function saveToStorage(form) {
    try {
      const toSave = {}
      for (const key of Object.keys(defaultValues)) {
        toSave[key] = form[key]
      }
      localStorage.setItem(storageKey, JSON.stringify(toSave))
    } catch { /* 忽略 */ }
  }

  function clearStorage() {
    try {
      localStorage.removeItem(storageKey)
    } catch { /* 忽略 */ }
  }

  return {
    loadStored,
    saveToStorage,
    clearStorage,
  }
}
