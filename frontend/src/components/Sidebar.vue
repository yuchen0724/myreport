<template>
  <!-- 登录页不渲染侧边栏 -->
  <div v-if="!isLoginPage" class="sidebar">
    <el-menu
      :default-active="activeMenu"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
      router
    >
      <!-- 静态系统菜单 -->
      <el-menu-item index="/">
        <el-icon><House /></el-icon>
        <span>仪表盘</span>
      </el-menu-item>
      
      <!-- 动态报表菜单 -->
      <el-sub-menu v-if="reportMenus.length > 0" index="reports">
        <template #title>
          <el-icon><TrendCharts /></el-icon>
          <span>报表中心</span>
        </template>
        <template v-for="menu in reportMenus" :key="menu.id">
          <!-- 有子菜单 -->
          <el-sub-menu v-if="menu.children && menu.children.length > 0" :index="'sub-' + menu.id">
            <template #title>
              <el-icon v-if="menu.icon"><component :is="menu.icon" /></el-icon>
              <span>{{ menu.name }}</span>
            </template>
            <el-menu-item 
              v-for="child in menu.children" 
              :key="child.id" 
              :index="child.path || '/report/' + child.id"
            >
              <el-icon v-if="child.icon"><component :is="child.icon" /></el-icon>
              <span>{{ child.name }}</span>
            </el-menu-item>
          </el-sub-menu>
          <!-- 无子菜单 -->
          <el-menu-item v-else :index="menu.path || '/report/' + menu.id">
            <el-icon v-if="menu.icon"><component :is="menu.icon" /></el-icon>
            <span>{{ menu.name }}</span>
          </el-menu-item>
        </template>
      </el-sub-menu>
      
      <!-- 系统管理菜单 -->
      <el-sub-menu index="system">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </template>
        <el-menu-item index="/dashboard/layouts">
          <el-icon><Monitor /></el-icon>
          <span>布局管理</span>
        </el-menu-item>
        <el-menu-item index="/datasources">
          <el-icon><DataLine /></el-icon>
          <span>数据源管理</span>
        </el-menu-item>
        <el-menu-item index="/proxy-servers">
          <el-icon><Connection /></el-icon>
          <span>代理服务器</span>
        </el-menu-item>
        <el-menu-item index="/templates">
          <el-icon><Folder /></el-icon>
          <span>模板管理</span>
        </el-menu-item>
        <el-menu-item index="/favorites">
          <el-icon><Star /></el-icon>
          <span>我的收藏</span>
        </el-menu-item>
        <el-menu-item index="/menus" v-if="isAdmin">
          <el-icon><Menu /></el-icon>
          <span>菜单管理</span>
        </el-menu-item>
        <el-menu-item index="/scheduled-reports">
          <el-icon><AlarmClock /></el-icon>
          <span>定时报表</span>
        </el-menu-item>
        <el-menu-item index="/subscriptions">
          <el-icon><Bell /></el-icon>
          <span>订阅推送</span>
        </el-menu-item>
        <el-menu-item index="/template-share">
          <el-icon><Share /></el-icon>
          <span>模板分享</span>
        </el-menu-item>
        <el-menu-item index="/pool-monitor" v-if="isAdmin">
          <el-icon><Monitor /></el-icon>
          <span>连接池监控</span>
        </el-menu-item>
        <el-menu-item index="/semantic-metrics">
          <el-icon><DataLine /></el-icon>
          <span>语义指标</span>
        </el-menu-item>
      </el-sub-menu>
      
      <!-- 工具菜单 -->
      <el-sub-menu index="tools">
        <template #title>
          <el-icon><Tools /></el-icon>
          <span>工具</span>
        </template>
        <el-menu-item index="/query">
          <el-icon><Document /></el-icon>
          <span>SQL 查询</span>
        </el-menu-item>
        <el-menu-item index="/nl2sql">
          <el-icon><ChatLineRound /></el-icon>
          <span>NL2SQL 查询</span>
        </el-menu-item>
        <el-menu-item index="/charts">
          <el-icon><TrendCharts /></el-icon>
          <span>图表查看器</span>
        </el-menu-item>
        <el-menu-item index="/async-export">
          <el-icon><Download /></el-icon>
          <span>异步导出</span>
        </el-menu-item>
        <el-menu-item index="/ai-analyst">
          <el-icon><MagicStick /></el-icon>
          <span>AI 分析师</span>
        </el-menu-item>
      </el-sub-menu>

      <!-- 销售预测 -->
      <el-sub-menu index="sales-prediction">
        <template #title>
          <el-icon><TrendCharts /></el-icon>
          <span>销售预测</span>
        </template>
        <el-menu-item index="/sales-forecast">
          <span>训练预测</span>
        </el-menu-item>
        <el-menu-item index="/forecast-results">
          <span>预测结果查询</span>
        </el-menu-item>
        <el-menu-item index="/model-compare">
          <span>模型对比</span>
        </el-menu-item>
      </el-sub-menu>

      <!-- RCA 根因分析 -->
      <el-sub-menu index="rca">
        <template #title>
          <el-icon><Search /></el-icon>
          <span>根因分析</span>
        </template>
        <el-menu-item index="/rca">
          <span>分析总览</span>
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </div>
</template>

<script>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { 
  House, Monitor, DataLine, Document, ChatLineRound, TrendCharts, 
  Folder, Share, Download, Setting, Menu, Tools, Connection, AlarmClock, Star, Bell, MagicStick, Search
} from '@element-plus/icons-vue'
import { useUserStore, useMenuStore } from '@/store'

export default {
  name: 'Sidebar',
  components: { 
    House, Monitor, DataLine, Document, ChatLineRound, TrendCharts, 
    Folder, Share, Download, Setting, Menu, Tools, Connection, AlarmClock, Star, Bell, MagicStick, Search
  },
  setup() {
    const route = useRoute()
    const userStore = useUserStore()
    const menuStore = useMenuStore()
    
    // 判断是否在登录页
    const isLoginPage = computed(() => route.path === '/login')
    const activeMenu = computed(() => route.path)
    const isAdmin = computed(() => {
      const result = userStore.hasRole(['admin'])
      return result
    })
    
    // 直接从 store 获取菜单（只有在非登录页才加载）
    const reportMenus = computed(() => menuStore.menus)
    
    // 首次加载菜单（非登录页才加载）
    onMounted(() => {
      if (!isLoginPage.value) {
        menuStore.loadMenus()
      }
    })
    
    return { 
      activeMenu, 
      reportMenus, 
      isAdmin,
      isLoginPage
    }
  }
}
</script>

<style scoped>
.sidebar {
  height: 100%;
  overflow-y: auto;
}

.sidebar::-webkit-scrollbar {
  width: 4px;
}
.sidebar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}

.el-menu {
  border-right: none;
}
</style>
