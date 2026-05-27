<template>
  <div class="mobile-dashboard">
    <!-- 顶部欢迎区 -->
    <div class="mobile-welcome">
      <h2>仪表盘</h2>
      <p class="subtitle">欢迎回来，{{ username }}</p>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="mobile-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 错误提示 -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon closable @close="error = ''" />

    <!-- 统计卡片 - 单列 -->
    <template v-else>
      <div class="stat-cards">
        <div class="stat-card" v-for="stat in stats" :key="stat.key">
          <div class="stat-icon" :style="{ background: stat.color }">
            <el-icon :size="24"><component :is="stat.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>

      <!-- 最近查询 -->
      <div class="section-card">
        <div class="section-header">
          <h3>最近查询</h3>
          <el-button text type="primary" size="small" @click="$router.push('/query')">
            查看全部
          </el-button>
        </div>
        <div v-if="dashboardData.recent_queries?.length" class="recent-list">
          <div
            v-for="item in dashboardData.recent_queries.slice(0, 5)"
            :key="item.id"
            class="recent-item"
          >
            <div class="recent-item-title">{{ item.data_source_name || '数据源#' + item.data_source_id }}</div>
            <div class="recent-item-desc">{{ item.sql?.substring(0, 60) }}{{ item.sql?.length > 60 ? '...' : '' }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无查询记录" :image-size="60" />
      </div>

      <!-- 最近模板 -->
      <div class="section-card">
        <div class="section-header">
          <h3>最近模板</h3>
          <el-button text type="primary" size="small" @click="$router.push('/templates')">
            查看全部
          </el-button>
        </div>
        <div v-if="dashboardData.recent_templates?.length" class="recent-list">
          <div
            v-for="item in dashboardData.recent_templates.slice(0, 5)"
            :key="item.id"
            class="recent-item"
            @click="$router.push(`/templates/${item.id}`)"
          >
            <div class="recent-item-title">{{ item.name }}</div>
            <div class="recent-item-desc">{{ item.description || '暂无描述' }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无模板" :image-size="60" />
      </div>

      <!-- 快速操作 -->
      <div class="quick-actions">
        <div class="action-btn" @click="$router.push('/query')">
          <el-icon :size="24"><Document /></el-icon>
          <span>SQL 查询</span>
        </div>
        <div class="action-btn" @click="$router.push('/nl2sql')">
          <el-icon :size="24"><ChatLineRound /></el-icon>
          <span>智能查询</span>
        </div>
        <div class="action-btn" @click="$router.push('/templates')">
          <el-icon :size="24"><Folder /></el-icon>
          <span>模板管理</span>
        </div>
        <div class="action-btn" @click="$router.push('/favorites')">
          <el-icon :size="24"><Star /></el-icon>
          <span>我的收藏</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/store'
import { getDashboardData } from '@/api/dashboard'
import {
  Document, ChatLineRound, Folder, Star,
  DataLine, Timer, Download
} from '@element-plus/icons-vue'

const userStore = useUserStore()
const username = computed(() => userStore.user?.username || '用户')

const loading = ref(true)
const error = ref('')
const dashboardData = ref({
  data_source_count: 0,
  query_count: 0,
  export_count: 0,
  template_count: 0,
  recent_queries: [],
  recent_templates: [],
})

const stats = computed(() => [
  { key: 'data_source_count', label: '数据源', value: dashboardData.value.data_source_count, icon: 'DataLine', color: '#409eff' },
  { key: 'query_count', label: '查询次数', value: dashboardData.value.query_count, icon: 'Timer', color: '#67c23a' },
  { key: 'export_count', label: '导出次数', value: dashboardData.value.export_count, icon: 'Download', color: '#e6a23c' },
  { key: 'template_count', label: '模板数量', value: dashboardData.value.template_count, icon: 'Folder', color: '#f56c6c' },
])

onMounted(async () => {
  try {
    const data = await getDashboardData()
    dashboardData.value = data
  } catch (err) {
    console.error('加载仪表盘失败:', err)
    error.value = '加载仪表盘数据失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.mobile-dashboard {
  padding: 16px;
  padding-bottom: 80px;
}

.mobile-welcome {
  margin-bottom: 20px;
}

.mobile-welcome h2 {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.mobile-welcome .subtitle {
  font-size: 14px;
  color: var(--text-secondary, #909399);
  margin: 0;
}

.mobile-loading {
  padding: 20px 0;
}

.stat-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary, #909399);
}

.section-card {
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.recent-item {
  padding: 10px 12px;
  background: var(--bg-secondary, #f5f7fa);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.recent-item:active {
  background: var(--border-color, #e4e7ed);
}

.recent-item-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-item-desc {
  font-size: 12px;
  color: var(--text-secondary, #909399);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 16px;
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 12px;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.action-btn:active {
  transform: scale(0.97);
}

.action-btn span {
  font-size: 13px;
  font-weight: 500;
}
</style>
