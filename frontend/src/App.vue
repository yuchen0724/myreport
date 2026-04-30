<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script>
import { onMounted } from 'vue'
import { useUserStore } from '@/store'

export default {
  name: 'App',
  setup() {
    const userStore = useUserStore()

    onMounted(() => {
      const token = localStorage.getItem('token')
      const user = localStorage.getItem('user')
      if (token && user) {
        userStore.setToken(token)
        userStore.setUser(JSON.parse(user))
      }
    })

    return { userStore }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

#app {
  height: 100vh;
  overflow: hidden;
}
</style>