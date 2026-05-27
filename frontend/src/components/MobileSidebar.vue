<template>
  <div class="mobile-sidebar-content">
    <!-- 用户信息 -->
    <div class="mobile-user-info">
      <div class="user-avatar">
        <el-icon :size="28"><User /></el-icon>
      </div>
      <div class="user-details">
        <div class="user-name">{{ user?.username || '用户' }}</div>
        <div class="user-role">{{ isAdmin ? '管理员' : '普通用户' }}</div>
      </div>
    </div>

    <!-- 菜单列表 -->
    <el-menu
      :default-active="activeMenu"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
      router
      @select="$emit('navigate')"
    >
      <el-menu-item index="/">
        <el-icon><House /></el-icon>
        <span>仪表盘</span>
      </el-menu-item>

      <el-menu-item index="/query">
        <el-icon><Document /></el-icon>
        <span>SQL 查询</span>
      </el-menu-item>

      <el-menu-item index="/nl2sql">
        <el-icon><ChatLineRound /></el-icon>
        <span>智能查询</span>
      </el-menu-item>

      <el-menu-item index="/templates">
        <el-icon><Folder /></el-icon>
        <span>模板管理</span>
      </el-menu-item>

      <el-menu-item index="/favorites">
        <el-icon><Star /></el-icon>
        <span>我的收藏</span>
      </el-menu-item>

      <!-- 动态报表菜单 -->
      <el-sub-menu v-if="reportMenus.length > 0" index="reports">
        <template #title>
          <el-icon><TrendCharts /></el-icon>
          <span>报表中心</span>
        </template>
        <template v-for="menu in reportMenus" :key="menu.id">
          <el-sub-menu v-if="menu.children && menu.children.length > 0" :index="'sub-' + menu.id">
            <template #title>
              <span>{{ menu.name }}</span>
            </template>
            <el-menu-item
              v-for="child in menu.children"
              :key="child.id"
              :index="child.path || '/report/' + child.id"
            >
              <span>{{ child.name }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="menu.path || '/report/' + menu.id">
            <span>{{ menu.name }}</span>
          </el-menu-item>
        </template>
      </el-sub-menu>

      <!-- 管理菜单 (仅管理员可见) -->
      <el-sub-menu v-if="isAdmin" index="system">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </template>
        <el-menu-item index="/datasources">
          <span>数据源管理</span>
        </el-menu-item>
        <el-menu-item index="/proxy-servers">
          <span>代理服务器</span>
        </el-menu-item>
        <el-menu-item index="/menus">
          <span>菜单管理</span>
        </el-menu-item>
        <el-menu-item index="/scheduled-reports">
          <span>定时报表</span>
        </el-menu-item>
        <el-menu-item index="/subscriptions">
          <span>订阅推送</span>
        </el-menu-item>
        <el-menu-item index="/pool-monitor">
          <span>连接池监控</span>
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore, useMenuStore } from '@/store'
import {
  House, Document, ChatLineRound, Folder, Star,
  TrendCharts, Setting, User
} from '@element-plus/icons-vue'

const emit = defineEmits(['navigate'])

const route = useRoute()
const userStore = useUserStore()
const menuStore = useMenuStore()

const activeMenu = computed(() => route.path)
const isAdmin = computed(() => userStore.hasRole(['admin']))
const user = computed(() => userStore.user)
const reportMenus = computed(() => menuStore.menus)

onMounted(() => {
  menuStore.loadMenus()
})
</script>

<style scoped>
.mobile-sidebar-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.mobile-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.user-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.user-name {
  font-size: 16px;
  font-weight: 600;
}

.user-role {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.el-menu {
  border-right: none;
  flex: 1;
}
</style>
