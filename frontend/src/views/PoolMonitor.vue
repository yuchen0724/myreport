<template>
  <div class="pool-monitor">
    <div class="toolbar">
      <h2>连接池监控</h2>
      <div class="toolbar-actions">
        <el-button @click="refreshData" :loading="loading" type="primary">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-switch
          v-model="autoRefresh"
          active-text="自动刷新"
          inactive-text=""
          @change="handleAutoRefresh"
        />
      </div>
    </div>

    <!-- 汇总统计卡片 -->
    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="card-icon active-icon">
              <el-icon><Connection /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ allMetrics.total_active }}</div>
              <div class="card-label">活跃连接数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="card-icon idle-icon">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ allMetrics.total_idle }}</div>
              <div class="card-label">空闲连接数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="card-icon waiting-icon">
              <el-icon><Clock /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ allMetrics.total_waiting }}</div>
              <div class="card-label">等待队列</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="card-icon pool-icon">
              <el-icon><DataLine /></el-icon>
            </div>
            <div class="card-info">
              <div class="card-value">{{ allMetrics.pools.length }}</div>
              <div class="card-label">数据源数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 连接池详情表格 -->
    <el-card class="pool-table-card">
      <el-table :data="allMetrics.pools" v-loading="loading" stripe>
        <el-table-column prop="data_source_name" label="数据源名称" width="180" />
        <el-table-column prop="data_source_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.data_source_type)" size="small">
              {{ row.data_source_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="连接池状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '活跃' : '未激活' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="活跃连接" width="100">
          <template #default="{ row }">
            <span class="metric-value active">{{ row.active_connections }}</span>
          </template>
        </el-table-column>
        <el-table-column label="空闲连接" width="100">
          <template #default="{ row }">
            <span class="metric-value idle">{{ row.idle_connections }}</span>
          </template>
        </el-table-column>
        <el-table-column label="等待队列" width="100">
          <template #default="{ row }">
            <span class="metric-value" :class="{ 'warning': row.waiting_queue_length > 0 }">
              {{ row.waiting_queue_length }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="平均查询时间" width="130">
          <template #default="{ row }">
            <span class="metric-value">{{ row.avg_query_time_ms }} ms</span>
          </template>
        </el-table-column>
        <el-table-column label="池大小" width="100">
          <template #default="{ row }">
            {{ row.pool_size }} / {{ row.max_overflow }}
          </template>
        </el-table-column>
        <el-table-column label="总连接" width="100">
          <template #default="{ row }">
            {{ row.total_connections }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)" type="primary" link>
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="连接池详情" width="600px">
      <template v-if="selectedPool">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="数据源">{{ selectedPool.data_source_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="getTypeTag(selectedPool.data_source_type)" size="small">
              {{ selectedPool.data_source_type }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedPool.is_active ? 'success' : 'danger'" size="small">
              {{ selectedPool.is_active ? '活跃' : '未激活' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="池大小">{{ selectedPool.pool_size }}</el-descriptions-item>
          <el-descriptions-item label="最大溢出">{{ selectedPool.max_overflow }}</el-descriptions-item>
          <el-descriptions-item label="活跃连接">
            <span class="metric-value active">{{ selectedPool.active_connections }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="空闲连接">
            <span class="metric-value idle">{{ selectedPool.idle_connections }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="等待队列">
            <span class="metric-value" :class="{ 'warning': selectedPool.waiting_queue_length > 0 }">
              {{ selectedPool.waiting_queue_length }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="平均查询时间">{{ selectedPool.avg_query_time_ms }} ms</el-descriptions-item>
          <el-descriptions-item label="总连接数">{{ selectedPool.total_connections }}</el-descriptions-item>
          <el-descriptions-item label="已检出">{{ selectedPool.checked_out }}</el-descriptions-item>
          <el-descriptions-item label="已归还">{{ selectedPool.checked_in }}</el-descriptions-item>
          <el-descriptions-item label="溢出数">{{ selectedPool.overflow }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Connection, CircleCheck, Clock, DataLine } from '@element-plus/icons-vue'
import { getAllPoolMetrics } from '@/api/pool_metrics'

const loading = ref(false)
const autoRefresh = ref(false)
const detailVisible = ref(false)
const selectedPool = ref(null)
let refreshTimer = null

const allMetrics = reactive({
  pools: [],
  total_active: 0,
  total_idle: 0,
  total_waiting: 0,
})

const refreshData = async () => {
  loading.value = true
  try {
    const data = await getAllPoolMetrics()
    Object.assign(allMetrics, data)
  } catch (error) {
    ElMessage.error('加载连接池指标失败')
  } finally {
    loading.value = false
  }
}

const handleAutoRefresh = (val) => {
  if (val) {
    refreshTimer = setInterval(refreshData, 5000)
  } else {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }
}

const getTypeTag = (type) => {
  const map = {
    'MYSQL': '',
    'DORIS': 'warning',
    'POSTGRESQL': 'success',
  }
  return map[type] || 'info'
}

const showDetail = (pool) => {
  selectedPool.value = pool
  detailVisible.value = true
}

onMounted(() => {
  refreshData()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.pool-monitor {
  padding: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar h2 {
  margin: 0;
  font-size: 20px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  height: 100px;
}

.card-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.card-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
}

.active-icon { background: linear-gradient(135deg, #409eff, #66b1ff); }
.idle-icon { background: linear-gradient(135deg, #67c23a, #85ce61); }
.waiting-icon { background: linear-gradient(135deg, #e6a23c, #ebb563); }
.pool-icon { background: linear-gradient(135deg, #909399, #b1b3b8); }

.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.card-label {
  font-size: 13px;
  color: #909399;
}

.pool-table-card {
  margin-bottom: 20px;
}

.metric-value {
  font-weight: bold;
}

.metric-value.active {
  color: #409eff;
}

.metric-value.idle {
  color: #67c23a;
}

.metric-value.warning {
  color: #e6a23c;
}
</style>
