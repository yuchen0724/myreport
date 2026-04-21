import { useUserStore } from "@/store"

export function isAuthenticated() {
  const userStore = useUserStore()
  return !!userStore.token
}

export function logout() {
  const userStore = useUserStore()
  userStore.logout()
}