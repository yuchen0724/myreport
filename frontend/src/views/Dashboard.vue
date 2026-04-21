<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="dashboard-content">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card>
            <div class="stat-card">
              <h3>数据源</h3>
              <p class="stat-number">{{ stats.dataSourceCount }}</p>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card>
            <div class="stat-card">
              <h3>查询次数</h3>
              <p class="stat-number">{{ stats.queryCount }}</p>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card>
            <div class="stat-card">
              <h3>导出次数</h3>
              <p class="stat-number">{{ stats.exportCount }}</p>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card>
            <div class="stat-card">
              <h3>模板数量</h3>
              <p class="stat-number">{{ stats.templateCount }}</p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </Layout>
</template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getDashboardStats } from '@/api/stats'

export default {
  name: 'Dashboard',
  components: { Layout, Header, Sidebar },
  setup() {
    const stats = ref({
      dataSourceCount: 0,
      queryCount: 0,
      exportCount: 0,
      templateCount: 0
    })

    const loadStats = async () => {
      try {
        const response = await getDashboardStats()
        // 转换后端返回的下划线命名为驼峰命名
        stats.value = {
          dataSourceCount: response.data_source_count,
          queryCount: response.query_count,
          exportCount: response.export_count,
          templateCount: response.template_count
        }
      } catch (error) {
        console.error('加载统计数据失败:', error)
        ElMessage.error('加载统计数据失败')
      }
    }

    onMounted(() => {
      loadStats()
    })

    return { stats }
  }
}
</script>

<style scoped>
.dashboard-content {
  padding: 20px;
}

.stat-card {
  text-align: center;
}

.stat-card h3 {
  font-size: 16px;
  color: #666;
  margin-bottom: 10px;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}
</style>