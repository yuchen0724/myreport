import { defineStore } from "pinia"
import { ref } from "vue"

export const useUserStore = defineStore("user", () => {
  const token = ref(localStorage.getItem("token") || "")
  const user = ref(JSON.parse(localStorage.getItem("user") || "null"))

  function setToken(newToken) {
    console.log('设置 Token:', newToken)
    token.value = newToken
    localStorage.setItem("token", newToken)
    console.log('Token 已保存到 localStorage')
  }

  function setUser(newUser) {
    console.log('设置用户:', newUser)
    user.value = newUser
    localStorage.setItem("user", JSON.stringify(newUser))
    console.log('用户已保存到 localStorage')
  }

  function logout() {
    token.value = ""
    user.value = null
    localStorage.removeItem("token")
    localStorage.removeItem("user")
  }

  return { token, user, setToken, setUser, logout }
})