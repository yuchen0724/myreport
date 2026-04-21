<template>
  <div class="sidebar">
    <el-menu
      :default-active="activeMenu"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
      router
    >
      <el-menu-item index="/">
        <el-icon><house /></el-icon>
        <span>仪表盘</span>
      </el-menu-item>
      <el-menu-item index="/datasources">
        <el-icon><data-line /></el-icon>
        <span>数据源管理</span>
      </el-menu-item>
      <el-menu-item index="/query">
        <el-icon><document /></el-icon>
        <span>SQL 查询</span>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { House, DataLine, Document } from '@element-plus/icons-vue'

export default {
  name: 'Sidebar',
  components: { House, DataLine, Document },
  setup() {
    const route = useRoute()
    const activeMenu = computed(() => route.path)

    return { activeMenu }
  }
}
</script>

<style scoped>
.sidebar {
  height: 100%;
}

.el-menu {
  border-right: none;
}
</style>