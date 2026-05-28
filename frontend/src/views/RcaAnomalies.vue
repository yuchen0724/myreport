<template>
  <div class="rca-anomalies">
    <el-page-header @back="$router.push('/rca')" style="margin-bottom: 16px">
      <template #content>
        <span>异常根因分析</span>
      </template>
    </el-page-header>

    <!-- 任务信息 -->
    <el-card v-if="task" style="margin-bottom: 16px">
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="任务ID">{{ task.task_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="task.status === 'completed' ? 'success' : 'danger'" size="small">
            {{ task.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="分析日期">{{ task.analysis_date }}</el-descriptions-item>
        <el-descriptions-item label="周期">{{ task.period_days }}天</el-descriptions-item>
        <el-descriptions-item label="异常数">
          <el-tag v-if="task.anomaly_count" type="danger">{{ task.anomaly_count }}</el-tag>
          <span v-else>0</span>
        </el-descriptions-item>
        <el-descriptions-item label="总体变化">
          <span v-if="task.summary?.total_change_pct != null"
                :class="task.summary.total_change_pct < 0 ? 'text-danger' : 'text-success'">
            {{ task.summary.total_change_pct }}%
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 异常列表 - 按维度分组 -->
    <el-card v-for="(group, dimType) in groupedAnomalies" :key="dimType" style="margin-bottom: 16px">
      <template #header>
        <span>{{ dimLabel[dimType] || dimType }}（{{ group.length }}）</span>
      </template>
      <el-table
        :data="group"
        v-loading="loading"
        style="width: 100%"
        row-key="id"
        @expand-change="handleExpand"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 12px 24px">
              <h4 style="margin: 0 0 8px">下钻详情</h4>
              <div v-if="row._drillLoading">加载中...</div>
              <div v-else-if="row._drillData && row._drillData.length">
                <el-table :data="row._drillData" size="small" border>
                  <el-table-column label="维度值" min-width="200">
                    <template #default="{ row: r }">
                      {{ r.dim_name ? r.dim_name + ' (' + r.dim_val + ')' : r.dim_val }}
                    </template>
                  </el-table-column>
                  <el-table-column label="当前值" width="120">
                    <template #default="{ row: r }">{{ formatVal(r.current_value ?? r.current_val) }}</template>
                  </el-table-column>
                  <el-table-column label="基线值" width="120">
                    <template #default="{ row: r }">{{ formatVal(r.baseline_value ?? r.baseline_val) }}</template>
                  </el-table-column>
                  <el-table-column label="变化" width="100">
                    <template #default="{ row: r }">
                      <span :class="r.change_pct < 0 ? 'text-danger' : 'text-success'">
                        {{ r.change_pct }}%
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="贡献度" width="100">
                    <template #default="{ row: r }">{{ r.contribution_pct }}%</template>
                  </el-table-column>
                </el-table>
              </div>
              <div v-else>无下钻数据</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="名称" min-width="200">
          <template #default="{ row }">
            {{ row.dimension_path.name || row.dimension_path[dimType] }}
          </template>
        </el-table-column>
        <el-table-column label="编码" width="120">
          <template #default="{ row }">
            {{ row.dimension_path[dimType] }}
          </template>
        </el-table-column>
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">{{ formatVal(row.current_value) }}</template>
        </el-table-column>
        <el-table-column label="基线值" width="120">
          <template #default="{ row }">{{ formatVal(row.baseline_value) }}</template>
        </el-table-column>
        <el-table-column label="变化" width="100">
          <template #default="{ row }">
            <span :class="row.change_pct < 0 ? 'text-danger' : 'text-success'">
              {{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="贡献度" width="100">
          <template #default="{ row }">{{ row.contribution_pct }}%</template>
        </el-table-column>
        <el-table-column label="严重度" width="100">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="!loading && anomalies.length === 0" description="未发现异常" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getRcaTask, getRcaAnomalies, rcaDrillDown, getRcaConfigs } from '@/api/rca'

const route = useRoute()
const taskId = route.params.taskId

const task = ref(null)
const anomalies = ref([])
const loading = ref(false)
const drillDimensions = ref([])  // 从配置获取的下钻维度列表

const dimLabel = {
  operation_category1_name: '品类异常',
  store_code: '门店异常',
  matnr: '商品异常',
}

const groupedAnomalies = computed(() => {
  const groups = {}
  for (const a of anomalies.value) {
    const dim = Object.keys(a.dimension_path).find(k => k !== 'name') || 'unknown'
    if (!groups[dim]) groups[dim] = []
    groups[dim].push(a)
  }
  // 按维度层级排序：品类 → 门店 → 商品
  const order = ['operation_category1_name', 'store_code', 'matnr']
  const sorted = {}
  for (const k of order) {
    if (groups[k]) sorted[k] = groups[k]
  }
  for (const k of Object.keys(groups)) {
    if (!sorted[k]) sorted[k] = groups[k]
  }
  return sorted
})

const formatVal = (v) => {
  if (v == null) return '-'
  return (v / 10000).toFixed(2) + '万'
}

const loadData = async () => {
  loading.value = true
  try {
    const [taskRes, anomalyRes, cfgRes] = await Promise.all([
      getRcaTask(taskId), getRcaAnomalies(taskId), getRcaConfigs()
    ])
    task.value = taskRes.data || taskRes
    anomalies.value = (anomalyRes.data || anomalyRes).map(a => ({
      ...a,
      _drillData: null,
      _drillLoading: false,
    }))
    // 获取当前任务对应的配置的下钻维度
    const configs = cfgRes.data || cfgRes
    const cfg = configs.find(c => c.id === task.value?.metric_config_id)
    drillDimensions.value = cfg?.drill_dimensions || ['operation_category1_name', 'store_code', 'matnr']
  } catch (e) {
    console.error('Load anomalies failed:', e)
  } finally {
    loading.value = false
  }
}

const handleExpand = async (row, expanded) => {
  if (expanded.length === 0 || row._drillData) return

  row._drillLoading = true
  try {
    const dim = Object.keys(row.dimension_path)[0]
    const dimVal = row.dimension_path[dim]
    // 从配置的维度列表中选下一个
    const dims = drillDimensions.value
    const curIdx = dims.indexOf(dim)
    const nextDim = curIdx >= 0 && curIdx < dims.length - 1 ? dims[curIdx + 1] : null
    if (!nextDim) {
      row._drillData = []
      return
    }
    const res = await rcaDrillDown({
      task_id: taskId,
      metric_name: row.metric_name,
      dimension: nextDim,
      filters: { [dim]: dimVal },
    })
    row._drillData = (res.data || res).rows || []
  } catch (e) {
    row._drillData = []
  } finally {
    row._drillLoading = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.rca-anomalies {
  padding: 16px;
}
.text-danger {
  color: #f56c6c;
  font-weight: bold;
}
.text-success {
  color: #67c23a;
  font-weight: bold;
}
</style>
