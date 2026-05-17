<template>
  <div class="dashboard-widget">
    <el-card v-if="isStatCard" shadow="hover">
      <div class="stat-card">
        <h3>{{ widget.title }}</h3>
        <p class="stat-number">{{ displayValue || statValue }}</p>
        <p v-if="customSqlInfo" class="stat-label">{{ customSqlInfo }}</p>
        <p v-if="customSqlError" class="stat-error">{{ customSqlError }}</p>
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
import { computed, ref, onMounted, watch } from 'vue'
import { useCountUp } from '@/composables/useCountUp'
import { executeSQL } from '@/api/query'

const STAT_CARD_TYPES = ['data_source_count', 'query_count', 'export_count', 'template_count']

export default {
  name: 'DashboardWidget',
  props: {
    widget: { type: Object, required: true },
    dashboardData: { type: Object, required: true },
    animationEnabled: { type: Boolean, default: true },
  },
  setup(props) {
    // ——— 判断组件类型 ———
    const isStatCard = computed(() => {
      if (props.widget.widget_type === 'stat') return true
      return STAT_CARD_TYPES.includes(props.widget.widget_type)
    })

    // ——— 自定义 SQL 检测 ———
    const extra = computed(() => props.widget.extra_config || {})
    const isCustomSql = computed(() => {
      return props.widget.widget_subtype === '__custom_sql__' && extra.value.customSql && extra.value.dataSourceId
    })

    // ——— 自定义 SQL 状态 ———
    const customSqlValue = ref(null)
    const customSqlInfo = ref('')
    const customSqlError = ref('')
    const customSqlLoaded = ref(false)

    const fetchCustomSqlValue = async () => {
      if (!isCustomSql.value) return
      const dsId = extra.value.dataSourceId
      const sql = extra.value.customSql
      customSqlError.value = ''
      try {
        const res = await executeSQL({
          data_source_id: dsId,
          sql: sql,
          page: 1,
          page_size: 1000,
          skip_deep_pagination_check: true,
        })
        const data = res.data || res
        if (data.rows && data.rows.length > 0) {
          // 取第一行第一列作为数值
          const raw = data.rows[0][0]
          customSqlValue.value = raw !== null && raw !== undefined ? raw : 0
          customSqlInfo.value = extra.value.expectedLabel || ''
        } else {
          customSqlValue.value = 0
          customSqlInfo.value = '（无数据）'
        }
      } catch (e) {
        console.error('自定义 SQL 查询失败:', e)
        customSqlError.value = e?.response?.data?.detail || e?.message || '查询失败'
        customSqlValue.value = null
      } finally {
        customSqlLoaded.value = true
      }
    }

    // ——— 最终显示的数值 ———
    const statValue = computed(() => {
      if (isCustomSql.value) {
        return customSqlValue.value ?? 0
      }
      // 新布局模式：从 subtype 取数
      if (props.widget.widget_subtype && props.widget.widget_type === 'stat') {
        return props.dashboardData[props.widget.widget_subtype] ?? 0
      }
      // 旧版兼容
      return props.dashboardData[props.widget.widget_type] ?? 0
    })

    // 数字滚动动画
    const { displayValue } = useCountUp(statValue, 1200, props.animationEnabled)

    const recentQueries = computed(() => props.dashboardData.recent_queries || [])
    const recentTemplates = computed(() => props.dashboardData.recent_templates || [])

    // ——— 生命周期 ———
    onMounted(() => {
      if (isCustomSql.value) {
        fetchCustomSqlValue()
      }
    })

    // watch widget 变化时重新查询
    watch(() => [props.widget.extra_config, props.widget.widget_subtype], () => {
      customSqlLoaded.value = false
      customSqlValue.value = null
      customSqlError.value = ''
      if (isCustomSql.value) {
        fetchCustomSqlValue()
      }
    }, { deep: true })

    return { isStatCard, displayValue, statValue, customSqlInfo, customSqlError, recentQueries, recentTemplates }
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
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.stat-error {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 4px;
}
.widget-body {
  min-height: 100px;
}
.widget-header {
  font-size: 15px;
  font-weight: 600;
}
</style>
