<template>
  <div class="dashboard-widget">
    <el-card v-if="isStatCard" shadow="hover">
      <div class="stat-card">
        <h3>{{ widget.title }}</h3>
        <p class="stat-number">{{ displayValue || statValue }}</p>
      </div>
    </el-card>
    <el-card v-else shadow="hover">
      <template #header>
        <div class="widget-header">
          <span>{{ widget.title }}</span>
        </div>
      </template>
      <div class="widget-body">
        <el-empty v-if="widget.widget_type === 'recent_queries' && !recentQueries.length" description="暂无查询记录" />
        <el-empty v-else-if="widget.widget_type === 'recent_templates' && !recentTemplates.length" description="暂无模板" />
        <el-table v-else-if="widget.widget_type === 'recent_queries'" :data="recentQueries" stripe size="small" style="width:100%">
          <el-table-column prop="query_text" label="查询" min-width="200" show-overflow-tooltip />
          <el-table-column prop="data_source_name" label="数据源" width="120" />
          <el-table-column prop="created_at" label="时间" width="170" />
        </el-table>
        <el-table v-else-if="widget.widget_type === 'recent_templates'" :data="recentTemplates" stripe size="small" style="width:100%">
          <el-table-column prop="name" label="模板名" min-width="150" />
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="created_at" label="创建时间" width="170" />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useCountUp } from '@/composables/useCountUp'

const STAT_CARD_TYPES = ['data_source_count', 'query_count', 'export_count', 'template_count']

export default {
  name: 'DashboardWidget',
  props: {
    widget: { type: Object, required: true },
    dashboardData: { type: Object, required: true },
    animationEnabled: { type: Boolean, default: true },
  },
  setup(props) {
    const isStatCard = computed(() => STAT_CARD_TYPES.includes(props.widget.widget_type))
    const statValue = computed(() => props.dashboardData[props.widget.widget_type] ?? 0)

    // 数字滚动动画
    const { displayValue } = useCountUp(statValue, 1200, props.animationEnabled)

    const recentQueries = computed(() => props.dashboardData.recent_queries || [])
    const recentTemplates = computed(() => props.dashboardData.recent_templates || [])

    return { isStatCard, displayValue, statValue, recentQueries, recentTemplates }
  }
}
</script>

<style scoped>
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
.widget-body {
  min-height: 100px;
}
.widget-header {
  font-size: 15px;
  font-weight: 600;
}
</style>
