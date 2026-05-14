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

    <!-- 多任务进度显示 -->
    <div v-if="taskProgresses.length > 0" class="progress-list">
      <el-card
        v-for="tp in taskProgresses"
        :key="tp.taskId"
        class="progress-card"
        shadow="never"
      >
        <div class="progress-body">
          <div class="progress-header">
            <div class="progress-info">
              <span class="progress-phase">{{ tp.phase }}</span>
              <span class="progress-percent">{{ tp.percent }}%</span>
            </div>
            <div class="progress-actions">
              <el-button
                v-if="tp.status === 'running'"
                size="small"
                type="danger"
                @click="handleStopTask(tp)"
              >
                停止
              </el-button>
            </div>
          </div>
          <el-progress
            :percentage="tp.percent"
            :status="tp.status === 'success' ? 'success' : tp.status === 'failed' ? 'exception' : undefined"
            :stroke-width="16"
            :text-inside="false"
            striped
            striped-flow
            :duration="6"
          />
          <div class="progress-detail">{{ tp.detail }}</div>
          <div class="progress-time" v-if="tp.createdAt">提交时间: {{ tp.createdAt }}</div>
        </div>
      </el-card>
    </div>

    <!-- 训练结束提示 -->
    <el-alert
      v-if="trainResult"
      :title="trainResult"
      :type="trainResult.includes('失败') || trainResult.includes('超时') ? 'error' : trainResult.includes('已提交') ? 'info' : 'success'"
      show-icon
      closable
      @close="trainResult = ''"
    />

    <!-- 训练历史区域 -->
    <el-card v-if="trainHistory.length > 0" class="history-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>训练历史</span>
        </div>
      </template>
      <el-table :data="trainHistory" border stripe style="width: 100%">
        <el-table-column prop="data_source_name" label="数据源" width="140" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ row.status === 'ready' ? '成功' : row.status === 'failed' ? '失败' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务ID" min-width="200">
          <template #default="{ row }">
            <code style="font-size: 12px">{{ row.task_id ? row.task_id.slice(0, 20) + '...' : '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="170" />
        <el-table-column prop="error_message" label="错误信息" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="handleDeleteHistory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
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
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { Refresh, TrendCharts } from '@element-plus/icons-vue'
import { trainModel, runPredict, getForecast, getTrainStatus, getMyTrainTasks, stopTrainTask, deleteTrainHistory, deleteTrainHistoryByTask } from '@/api/prediction'
import { getDataSourceList } from '@/api/data_source'
import { ElMessageBox, ElMessage } from 'element-plus'
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
    // 兼容旧代码：taskProgress 引用保持不变（但不再使用）
    const taskProgress = ref(null)
    // 多任务进度列表
    const taskProgresses = ref([])
    // 训练历史（已完成的任务列表）
    const trainHistory = ref([])
    let _pollingTaskId = null  // 防重复轮询标记
    let _trainingLock = false  // 防重复提交训练
    let _pollingInterval = null  // 统一轮询定时器
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

    // 统一轮询：每5秒查询所有 active 任务
    function startPolling() {
      if (_pollingInterval) return
      _pollingInterval = setInterval(async () => {
        const tasks = taskProgresses.value
        if (tasks.length === 0) {
          stopPolling()
          return
        }
        for (const tp of tasks) {
          if (tp.status !== 'running') continue
          try {
            const statusRes = await getTrainStatus(tp.taskId)
            const s = statusRes.data || statusRes
            tp.percent = s.percent || 0
            tp.phase = s.phase || '运行中'
            tp.detail = s.detail || ''
            if (s.status === 'success') {
              tp.status = 'success'
              tp.percent = 100
              tp.phase = '完成'
              // 从活动列表移除，加入历史
              removeFromActive(tp.taskId)
              addToHistory({
                status: 'ready',
                task_id: tp.taskId,
                model_id: s.model_id || tp.modelId,
                created_at: tp.createdAt,
                data_source_name: tp.dataSourceName,
              })
              trainResult.value = `模型训练成功！model_id=${s.model_id}`
            } else if (s.status === 'failed') {
              tp.status = 'failed'
              // 从活动列表移除，加入历史
              removeFromActive(tp.taskId)
              addToHistory({
                status: 'failed',
                task_id: tp.taskId,
                model_id: s.model_id || tp.modelId,
                created_at: tp.createdAt,
                error_message: s.error || '未知错误',
                data_source_name: tp.dataSourceName,
              })
              trainResult.value = `训练失败: ${s.error || '未知错误'}`
            }
          } catch {
            // 状态查询失败，继续
          }
        }
      }, 5000)
    }

    function stopPolling() {
      if (_pollingInterval) {
        clearInterval(_pollingInterval)
        _pollingInterval = null
        _pollingTaskId = null
      }
    }

    function removeFromActive(taskId) {
      const idx = taskProgresses.value.findIndex(t => t.taskId === taskId)
      if (idx !== -1) {
        taskProgresses.value.splice(idx, 1)
      }
    }

    function addToHistory(item) {
      // 去重：避免重复添加
      const exists = trainHistory.value.find(h => h.task_id === item.task_id)
      if (!exists) {
        trainHistory.value.unshift(item)
        // 最多保留10条
        if (trainHistory.value.length > 10) {
          trainHistory.value = trainHistory.value.slice(0, 10)
        }
      }
    }

    async function handleStopTask(tp) {
      try {
        await ElMessageBox.confirm(
          `确认停止训练任务 "${tp.taskId.slice(0, 12)}..." 吗？`,
          '确认停止',
          { confirmButtonText: '确认停止', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return // 用户取消
      }
      try {
        const stopRes = await stopTrainTask(tp.taskId)
        ElMessage.success('训练任务已停止')
        // 从活动列表移除
        const taskId = tp.taskId
        const dataSourceName = tp.dataSourceName
        const createdAt = tp.createdAt
        const modelId = (stopRes && stopRes.model_id) || tp.modelId
        removeFromActive(taskId)
        addToHistory({
          status: 'failed',
          task_id: taskId,
          model_id: modelId,
          created_at: createdAt,
          error_message: '用户手动停止',
          data_source_name: dataSourceName,
        })
        trainResult.value = '训练已停止'
      } catch (e) {
        ElMessage.error(`停止任务失败: ${e.message || e}`)
      }
    }

    async function handleDeleteHistory(row) {
      const modelId = row.model_id
      const taskId = row.task_id
      console.log('[delete] row:', { modelId, taskId })
      if (!modelId && !taskId) {
        ElMessage.warning('该记录缺少标识信息，无法删除')
        return
      }
      try {
        await ElMessageBox.confirm(
          '确认删除该训练历史记录吗？',
          '确认删除',
          { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return // 用户取消
      }
      try {
        if (modelId) {
          console.log('[delete] calling deleteTrainHistory with modelId:', modelId)
          await deleteTrainHistory(modelId)
        } else {
          console.log('[delete] calling deleteTrainHistoryByTask with taskId:', taskId)
          await deleteTrainHistoryByTask(taskId)
        }
        // 成功删除后从本地列表移除
        const idx = trainHistory.value.findIndex(
          h => (modelId && h.model_id === modelId) || (taskId && h.task_id === taskId)
        )
        console.log('[delete] found in trainHistory at index:', idx)
        if (idx !== -1) trainHistory.value.splice(idx, 1)
        ElMessage.success('删除成功')
        console.log('[delete] after removal, trainHistory length:', trainHistory.value.length)
      } catch (e) {
        console.error('[delete] failed:', e)
        ElMessage.error(`删除失败: ${e.message || e}`)
      }
    }

    async function handleTrain() {
      if (_trainingLock) return
      _trainingLock = true
      training.value = true
      trainResult.value = ''
      // 不清除 _pollingTaskId 以防止新的幽灵轮询；只清除 trainResult
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

        // 找到数据源名称
        const ds = dataSources.value.find(d => d.id === form.value.dataSourceId)
        const dsName = ds ? ds.name : `数据源#${form.value.dataSourceId}`

        // 加入多任务列表
        const newTask = {
          taskId,
          percent: 0,
          phase: '初始化',
          detail: '任务已提交',
          status: 'running',
          createdAt: new Date().toLocaleString(),
          dataSourceName: dsName,
        }
        taskProgresses.value.push(newTask)

        // 开始轮询（如果尚未开始）
        startPolling()
      } catch (e) {
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

    onBeforeUnmount(() => {
      stopPolling()
    })

    async function checkRunningTasks() {
      // 从 API 查询后端 running 的任务
      try {
        const tasksRes = await getMyTrainTasks()
        const list = Array.isArray(tasksRes) ? tasksRes : (tasksRes.data || [])
        let hasRunning = false
        for (const t of list) {
          if (t.status === 'training' && t.task_id) {
            hasRunning = true
            // 检查是否已经在列表中
            const exists = taskProgresses.value.find(p => p.taskId === t.task_id)
            if (!exists) {
              const progress = t.progress || {}
              taskProgresses.value.push({
                taskId: t.task_id,
                modelId: t.model_id,
                percent: progress.percent || 0,
                phase: progress.phase || '正在恢复',
                detail: progress.detail || '查询任务状态...',
                status: 'running',
                createdAt: t.created_at ? new Date(t.created_at).toLocaleString() : '',
                dataSourceName: t.data_source_name || '',
              })
            }
          } else if (t.status === 'ready' || t.status === 'failed') {
            // 加入历史
            addToHistory(t)
          }
        }
        if (hasRunning) {
          trainResult.value = '检测到后台运行中的任务，正在恢复进度...'
          startPolling()
        }
      } catch {
        // 静默失败
      }
    }

    return {
      form, dataSources, training, predicting, loading, trainResult, taskProgress,
      taskProgresses, trainHistory,
      forecastData, total, page, pageSize, chartRef, selectedStores, storeOptions,
      handleTrain, handlePredict, handleRefresh, loadForecast, handleStopTask,
      handleDeleteHistory,
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
.progress-list {
  margin-bottom: 16px;
}
.progress-card {
  margin-bottom: 12px;
}
.progress-body {
  padding: 4px 0;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  flex: 1;
  font-size: 14px;
  margin-right: 12px;
}
.progress-actions {
  flex-shrink: 0;
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
.progress-time {
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.history-card {
  margin-bottom: 16px;
}
</style>
