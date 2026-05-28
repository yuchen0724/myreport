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

    <!-- 异常列表 -->
    <el-card>
      <template #header><span>异常发现</span></template>

      <el-table
        :data="anomalies"
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
                  <el-table-column prop="dim_val" label="维度值" width="200" />
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

        <el-table-column label="维度" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="(v, k) in row.dimension_path" :key="k" size="small" style="margin: 2px">
              {{ k }}: {{ v }}
            </el-tag>
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

      <el-empty v-if="!loading && anomalies.length === 0" description="未发现异常" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getRcaTask, getRcaAnomalies, rcaDrillDown } from '@/api/rca'

const route = useRoute()
const taskId = route.params.taskId

const task = ref(null)
const anomalies = ref([])
const loading = ref(false)

const formatVal = (v) => {
  if (v == null) return '-'
  if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + '万'
  return v.toFixed(2)
}

const loadData = async () => {
  loading.value = true
  try {
    const [taskRes, anomalyRes] = await Promise.all([getRcaTask(taskId), getRcaAnomalies(taskId)])
    task.value = taskRes.data || taskRes
    anomalies.value = (anomalyRes.data || anomalyRes).map(a => ({
      ...a,
      _drillData: null,
      _drillLoading: false,
    }))
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
    const res = await rcaDrillDown({
      task_id: taskId,
      metric_name: row.metric_name,
      dimension: dim,
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
