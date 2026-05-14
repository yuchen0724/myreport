<template>
  <div class="sales-forecast">
    <el-page-header title="返回" @back="$router.push('/')" :content="'销售预测'" />

    <!-- 操作区域 -->
    <el-card class="action-card" shadow="never">
      <el-form :model="form" label-width="120px" inline>
        <el-form-item label="数据源">
          <el-select v-model="form.dataSourceId" placeholder="选择数据源" style="width: 240px">
            <el-option
              v-for="ds in dataSources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="训练天数">
          <el-input-number v-model="form.trainDays" :min="30" :max="730" :step="30" />
        </el-form-item>
        <el-form-item label="预测天数">
          <el-input-number v-model="form.forecastDays" :min="7" :max="365" :step="7" />
        </el-form-item>
        <el-form-item label="数据表名">
          <el-input v-model="form.tableName" placeholder="可选，默认: 库名.ads_cockpit_fd_store_ware_d" style="width: 320px" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleTrain" :loading="training" :disabled="!form.dataSourceId">
            <el-icon><Refresh /></el-icon> 训练模型
          </el-button>
          <el-button type="success" @click="handlePredict" :loading="predicting" :disabled="!form.dataSourceId" style="margin-left: 8px">
            <el-icon><TrendCharts /></el-icon> 运行预测
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 训练进度显示 -->
    <el-card v-if="taskProgress || trainResult" class="progress-card" shadow="never">
      <div class="progress-body">
        <!-- 有进度时显示进度条 -->
        <template v-if="taskProgress">
          <div class="progress-info">
            <span class="progress-phase">{{ taskProgress.phase }}</span>
            <span class="progress-percent">{{ taskProgress.percent }}%</span>
          </div>
          <el-progress
            :percentage="taskProgress.percent"
            :status="taskProgress.status === 'success' ? 'success' : taskProgress.status === 'failed' ? 'exception' : undefined"
            :stroke-width="16"
            :text-inside="false"
            striped
            striped-flow
            :duration="6"
          />
          <div class="progress-detail">{{ taskProgress.detail }}</div>
        </template>

        <!-- 训练结束提示（覆盖进度条） -->
        <el-alert
          v-if="trainResult"
          :title="trainResult"
          :type="trainResult.includes('失败') || trainResult.includes('超时') ? 'error' : trainResult.includes('已提交') ? 'info' : 'success'"
          show-icon
          closable
          @close="trainResult = ''; taskProgress = null"
        />
      </div>
    </el-card>

    <!-- 预测结果图表 -->
    <el-card v-if="forecastData.length > 0" class="chart-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>预测趋势图</span>
          <div>
            <el-checkbox-group v-model="selectedStores" size="small">
              <el-checkbox
                v-for="s in storeOptions"
                :key="s.value"
                :label="s.value"
                border
              >{{ s.label }}</el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </template>
      <div ref="chartRef" style="height: 400px" />
    </el-card>

    <!-- 预测结果表格 -->
    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>预测明细</span>
          <el-button size="small" @click="handleRefresh" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <el-table :data="forecastData" border stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="store_code" label="门店" width="100" />
        <el-table-column prop="matnr" label="商品编码" width="120" />
        <el-table-column prop="forecast_date" label="预测日期" width="120" />
        <el-table-column prop="predicted_value" label="预测值" width="120">
          <template #default="{ row }">
            {{ row.predicted_value?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="lower_bound" label="下限" width="120">
          <template #default="{ row }">
            {{ row.lower_bound !== null ? row.lower_bound.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="upper_bound" label="上限" width="120">
          <template #default="{ row }">
            {{ row.upper_bound !== null ? row.upper_bound.toFixed(2) : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadForecast"
        />
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { Refresh, TrendCharts } from '@element-plus/icons-vue'
import { trainModel, runPredict, getForecast, getTrainStatus, getMyTrainTasks } from '@/api/prediction'
import { getDataSourceList } from '@/api/data_source'
import * as echarts from 'echarts'

export default {
  name: 'SalesForecast',
  components: { Refresh, TrendCharts },
  setup() {
    const form = ref({
      dataSourceId: null,
      trainDays: 365,
      forecastDays: 30,
      tableName: '',
    })
    const dataSources = ref([])
    const training = ref(false)
    const predicting = ref(false)
    const loading = ref(false)
    const trainResult = ref('')
    const taskProgress = ref(null)
    let _pollingTaskId = null  // 防重复轮询标记
    let _trainingLock = false  // 防重复提交训练
    const forecastData = ref([])
    const total = ref(0)
    const page = ref(1)
    const pageSize = ref(50)
    const chartRef = ref(null)
    const selectedStores = ref([])
    let chartInstance = null

    const storeOptions = computed(() => {
      const stores = [...new Set(forecastData.value.map(d => d.store_code))]
      return stores.map(s => ({ label: s, value: s }))
    })

    // 初始化时选中所有门店
    watch(storeOptions, (opts) => {
      if (opts.length > 0 && selectedStores.value.length === 0) {
        selectedStores.value = opts.map(o => o.value)
      }
    })

    async function loadDataSources() {
      try {
        const res = await getDataSourceList()
        dataSources.value = Array.isArray(res) ? res : (res.data || [])
      } catch { /* silent */ }
    }

    async function loadForecast() {
      loading.value = true
      try {
        const res = await getForecast({
          data_source_id: form.value.dataSourceId,
          page: page.value,
          page_size: pageSize.value,
        })
        const data = res.data || res
        forecastData.value = data.items || []
        total.value = data.total || 0
      } catch { /* silent */ }
      finally { loading.value = false }
    }

    function renderChart() {
      if (!chartRef.value || forecastData.value.length === 0) return
      const filtered = forecastData.value.filter(d => selectedStores.value.includes(d.store_code))
      if (filtered.length === 0) return

      // 按日期排序
      filtered.sort((a, b) => a.forecast_date.localeCompare(b.forecast_date))

      // 分组
      const groups = {}
      for (const d of filtered) {
        const key = `${d.store_code}-${d.matnr}`
        if (!groups[key]) groups[key] = []
        groups[key].push(d)
      }

      const keys = Object.keys(groups).slice(0, 10) // 最多10条线
      const xData = [...new Set(filtered.map(d => d.forecast_date))].sort()

      const series = keys.map(key => {
        const items = groups[key]
        return {
          name: key,
          type: 'line',
          smooth: true,
          data: xData.map(date => {
            const found = items.find(i => i.forecast_date === date)
            return found ? +found.predicted_value.toFixed(2) : null
          }),
          markArea: items.length > 0 && items[0].lower_bound !== null ? {
            itemStyle: { color: 'rgba(0, 100, 250, 0.08)' },
            data: xData.map(date => {
              const found = items.find(i => i.forecast_date === date)
              return found && found.lower_bound !== null
                ? [{ yAxis: found.lower_bound }, { yAxis: found.upper_bound }]
                : []
            }).filter(Boolean),
          } : undefined,
        }
      })

      const option = {
        tooltip: { trigger: 'axis' },
        legend: { type: 'scroll', bottom: 0 },
        grid: { left: 60, right: 20, bottom: 60, top: 20 },
        xAxis: { type: 'category', data: xData, axisLabel: { rotate: 45 } },
        yAxis: { type: 'value', name: '预测值' },
        series,
      }

      if (!chartInstance) {
        chartInstance = echarts.init(chartRef.value)
      }
      chartInstance.setOption(option, true)
    }

    watch(selectedStores, () => nextTick(renderChart), { deep: true })

    async function handleTrain() {
      if (_trainingLock) return
      _trainingLock = true
      training.value = true
      trainResult.value = ''
      taskProgress.value = null
      // 清除正在轮询的任务，让新任务能启动轮询
      _pollingTaskId = null
      try {
        const tableName = form.value.tableName.trim() || null
        const res = await trainModel(form.value.dataSourceId, form.value.trainDays, tableName)
        const taskId = res.task_id || (res.data && res.data.task_id)
        if (!taskId) {
          trainResult.value = '模型训练成功！'
          return
        }

        // 保存 taskId 到 localStorage，用于页面刷新后恢复进度
        localStorage.setItem('lastTrainTaskId', taskId)

        // 先显示一个初始进度
        taskProgress.value = { percent: 0, phase: '初始化', detail: '任务已提交', status: 'running' }

        await pollTaskProgress(taskId)
      } catch (e) {
        taskProgress.value = null
        trainResult.value = `训练失败: ${e.message || e}`
      } finally { training.value = false; _trainingLock = false }
    }

    async function handlePredict() {
      predicting.value = true
      trainResult.value = ''
      try {
        const tableName = form.value.tableName.trim() || null
        const res = await runPredict(form.value.dataSourceId, form.value.forecastDays, tableName)
        trainResult.value = `预测成功！共 ${res.count || res.data?.count || 0} 条记录`
        await loadForecast()
        await nextTick(renderChart)
      } catch (e) {
        trainResult.value = `预测失败: ${e.message || e}`
      } finally { predicting.value = false }
    }

    function handleRefresh() {
      loadForecast()
    }

    onMounted(() => {
      loadDataSources()
      checkRunningTasks()
    })

    async function checkRunningTasks() {
      // 从 API 查询后端 running 的任务
      try {
        const tasksRes = await getMyTrainTasks()
        const list = Array.isArray(tasksRes) ? tasksRes : (tasksRes.data || [])
        const running = list.find(t => t.status === 'training')
        if (running && running.task_id) {
          localStorage.setItem('lastTrainTaskId', running.task_id)
          trainResult.value = `检测到后台运行中的任务 (${running.task_id.slice(0, 8)}...)，正在恢复进度...`
          await pollTaskProgress(running.task_id)
        }
      } catch {
        // 静默失败
      }
    }

    async function pollTaskProgress(taskId) {
      // 如果已经有其他任务在轮询，放弃当前请求
      if (_pollingTaskId && _pollingTaskId !== taskId) {
        return
      }
      _pollingTaskId = taskId
      taskProgress.value = { percent: 0, phase: '正在恢复', detail: '查询任务状态...', status: 'running' }

      const maxWait = 600000
      const interval = 1500
      const start = Date.now()

      while (Date.now() - start < maxWait) {
        await new Promise(r => setTimeout(r, interval))
        try {
          const statusRes = await getTrainStatus(taskId)
          const s = statusRes.data || statusRes

          if (s.status === 'success') {
            _pollingTaskId = null
            localStorage.removeItem('lastTrainTaskId')
            taskProgress.value = { percent: 100, phase: '完成', detail: s.detail || '', status: 'success' }
            trainResult.value = `模型训练成功！model_id=${s.model_id}`
            return
          }
          if (s.status === 'failed') {
            _pollingTaskId = null
            localStorage.removeItem('lastTrainTaskId')
            taskProgress.value = null
            trainResult.value = `训练失败: ${s.error || '未知错误'}`
            return
          }
          taskProgress.value = {
            percent: s.percent || 0,
            phase: s.phase || '运行中',
            detail: s.detail || '',
            status: 'running',
          }
        } catch {
          // 状态查询失败，继续轮询
        }
      }
      taskProgress.value = null
      trainResult.value = '训练超时，请稍后重新查询'
      _pollingTaskId = null
    }

    return {
      form, dataSources, training, predicting, loading, trainResult, taskProgress,
      forecastData, total, page, pageSize, chartRef, selectedStores, storeOptions,
      handleTrain, handlePredict, handleRefresh, loadForecast,
    }
  }
}
</script>

<style scoped>
.sales-forecast {
  padding: 16px;
}
.action-card {
  margin: 16px 0;
}
.chart-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.progress-card {
  margin-bottom: 16px;
}
.progress-body {
  padding: 4px 0;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}
.progress-phase {
  color: var(--el-text-color-primary);
  font-weight: 500;
}
.progress-percent {
  color: var(--el-text-color-secondary);
}
.progress-detail {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
