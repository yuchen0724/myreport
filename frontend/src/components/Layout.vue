<template>
  <div class="layout">
    <div class="header">
      <slot name="header" />
    </div>
    <div class="main">
      <div class="sidebar">
        <slot name="sidebar" />
      </div>
      <div class="content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Layout'
}
</script>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.header {
  height: 60px;
  background: #409eff;
  color: white;
}

.main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 200px;
  background: #304156;
  color: white;
}

.content {
  flex: 1;
  overflow-y: auto;
  background: #f0f2f5;
}
</style>