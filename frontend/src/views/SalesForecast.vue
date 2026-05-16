<template>
  <div class="sales-forecast">
    <el-page-header title="返回" @back="$router.push('/')" :content="'销售预测'" />

    <!-- 操作区域 -->
    <el-card class="action-card" shadow="never">
      <el-form :model="form" label-width="120px" inline>
        <el-form-item label="数据源">
          <el-select v-model="form.dataSourceId" placeholder="选择数据源" style="width: 240px" @change="onDataSourceChange">
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
          <el-button type="warning" @click="handleTrainAndPredict" :loading="trainAndPredictLoading" :disabled="!form.dataSourceId">
            <el-icon><Refresh /></el-icon> 训练并预测
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 多任务进度显示（训练+预测） -->
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
              <el-tag size="small" :type="tp.taskType === 'predict' ? 'success' : tp.taskType === 'train-and-predict' ? 'warning' : 'primary'" style="margin-left: 8px">
                {{ tp.taskType === 'predict' ? '预测' : tp.taskType === 'train-and-predict' ? '训练+预测' : '训练' }}
              </el-tag>
              <span class="progress-percent">{{ tp.percent }}%</span>
            </div>
            <div class="progress-actions">
              <el-button
                v-if="tp.status === 'running' && tp.taskType !== 'predict'"
                size="small"
                type="danger"
                @click="handleStopTask(tp)"
              >
                停止
              </el-button>
              <el-button
                v-if="tp.status === 'failed' || tp.status === 'success' || (tp.status === 'running' && (tp.taskType === 'predict' || tp.taskType === 'train-and-predict'))"
                size="small"
                type="warning"
                plain
                @click="handleDeleteProgress(tp)"
              >
                删除
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

    <!-- 提示消息 -->
    <el-alert
      v-if="resultMsg"
      :title="resultMsg"
      :type="resultMsg.includes('失败') || resultMsg.includes('超时') ? 'error' : resultMsg.includes('已提交') ? 'info' : 'success'"
      show-icon
      closable
      @close="resultMsg = ''"
    />

    <!-- 任务历史 -->
    <el-card v-if="taskHistory.length > 0" class="history-card" shadow="never">
      <template #header>
        <div class="card-header"><span>任务历史</span></div>
      </template>
      <el-table :data="taskHistory" border stripe style="width: 100%">
        <el-table-column prop="data_source_name" label="数据源" width="140" />
        <el-table-column label="模型ID" width="80">
          <template #default="{ row }"><el-tag size="small">{{ row.model_id ?? '-' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' || row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'ready' || row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="指标" width="200">
          <template #default="{ row }">
            <span style="font-size: 12px">
              <template v-if="row.metrics">
                MAE={{ row.metrics.mae?.toFixed(2) }}
              </template>
              <template v-if="row.result_count">
                <template v-if="row.metrics"> | </template>
                预测{{ row.result_count }}条
              </template>
              <template v-if="!row.metrics && !row.result_count">-</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务ID" min-width="150">
          <template #default="{ row }">
            <code style="font-size: 12px">{{ row.task_id ? row.task_id.slice(0, 16) + '...' : '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="165" />
        <el-table-column prop="error_message" label="错误" min-width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="handleDeleteHistory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>


  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { trainAndPredict, getTrainStatus, getPredictStatus, getMyTrainTasks, stopTrainTask, getForecastHistory, getForecastRunning, deleteForecastProgress, deleteTrainHistory, deleteTrainHistoryByTask } from '@/api/prediction'
import { getDataSourceList } from '@/api/data_source'
import { ElMessageBox, ElMessage } from 'element-plus'

export default {
  name: 'SalesForecast',
  components: { Refresh },
  setup() {
    const STORAGE_KEY = 'sales_forecast_form'

    // 从 localStorage 恢复表单状态，不重置用户选择
    function loadStoredForm() {
      try {
        const saved = localStorage.getItem(STORAGE_KEY)
        if (saved) {
          const parsed = JSON.parse(saved)
          return {
            dataSourceId: parsed.dataSourceId ?? null,
            trainDays: parsed.trainDays ?? 365,
            forecastDays: parsed.forecastDays ?? 30,
            tableName: parsed.tableName ?? '',
          }
        }
      } catch { /* 忽略 */ }
      return { dataSourceId: null, trainDays: 365, forecastDays: 30, tableName: '' }
    }

    const form = ref(loadStoredForm())

    // 表单值变化时自动保存到 localStorage
    watch(form.value, () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(form.value))
    }, { deep: true })
    const dataSources = ref([])
    const trainAndPredictLoading = ref(false)
    const loading = ref(false)
    const resultMsg = ref('')
    const taskProgress = ref(null)
    const taskProgresses = ref([])
    const taskHistory = ref([])
    let _trainAndPredictLock = false
    let _pollingInterval = null
    let _pollingTaskId = null


    async function loadDataSources() {
      try {
        const res = await getDataSourceList()
        dataSources.value = Array.isArray(res) ? res : (res.data || [])
      } catch { /* silent */ }
    }

    async function onDataSourceChange() {
      await loadHistory()
    }

    async function loadHistory() {
      // 同时加载训练记录和预测记录，按 model_id 去重
      let all = []
      try {
        const [tasksRes, forecastRes] = await Promise.all([
          getMyTrainTasks(false),
          getForecastHistory({ _t: Date.now() })
        ])
        const tasks = Array.isArray(tasksRes) ? tasksRes : (tasksRes.data || [])
        const forecasts = Array.isArray(forecastRes) ? forecastRes : (forecastRes.data || [])
        all = [...tasks, ...forecasts]
      } catch { /* silent */ }

      // 按 model_id 合并：同时有训练（metrics）和预测（result_count）记录时合并为一条
      const merged = new Map()
      for (const item of all) {
        const key = item.model_id || item.task_id
        if (!key) { merged.set(`_${Math.random()}`, item); continue }
        if (merged.has(key)) {
          const existing = merged.get(key)
          if (item.metrics) existing.metrics = item.metrics
          if (item.result_count) existing.result_count = item.result_count
          if (!existing.data_source_name) existing.data_source_name = item.data_source_name
        } else {
          merged.set(key, { ...item })
        }
      }

      taskHistory.value = [...merged.values()]
        .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
        .slice(0, 20)
    }

    // 统一轮询
    function startPolling() {
      if (_pollingInterval) return
      _pollingInterval = setInterval(async () => {
        const tasks = taskProgresses.value
        if (tasks.length === 0) { stopPolling(); return }
        for (const tp of tasks) {
          if (tp.status !== 'running') continue
          try {
            const statusFn = tp.taskType === 'predict' ? getPredictStatus : getTrainStatus
            const statusRes = await statusFn(tp.taskId)
            const s = statusRes.data || statusRes
            tp.percent = s.percent || 0
            tp.phase = s.phase || '运行中'
            tp.detail = s.detail || ''
            if (s.status === 'success') {
              tp.status = 'success'; tp.percent = 100; tp.phase = '完成'
              removeFromActive(tp.taskId)
              if (tp.taskType === 'predict') {
                resultMsg.value = '预测完成！'
                await loadHistory()
              } else if (tp.taskType === 'train-and-predict') {
                resultMsg.value = `训练+预测完成！model_id=${s.model_id || s.modelId || ''}`
                addToHistory({ status: 'ready', task_id: tp.taskId, model_id: s.model_id || tp.modelId, created_at: tp.createdAt, data_source_name: tp.dataSourceName })
                await loadHistory()
              } else {
                addToHistory({ status: 'ready', task_id: tp.taskId, model_id: s.model_id || tp.modelId, created_at: tp.createdAt, data_source_name: tp.dataSourceName })
                resultMsg.value = `模型训练成功！model_id=${s.model_id}`
                loadHistory()
              }
              loadModelOptions()
            } else if (s.status === 'failed') {
              tp.status = 'failed'
              removeFromActive(tp.taskId)
              if (tp.taskType === 'predict') {
                resultMsg.value = `预测失败: ${s.error || '未知错误'}`
              } else if (tp.taskType === 'train-and-predict') {
                addToHistory({ status: 'failed', task_id: tp.taskId, model_id: s.model_id || tp.modelId, created_at: tp.createdAt, error_message: s.error || '未知错误', data_source_name: tp.dataSourceName })
                resultMsg.value = `训练+预测失败: ${s.error || '未知错误'}`
                loadHistory()
              } else {
                addToHistory({ status: 'failed', task_id: tp.taskId, model_id: s.model_id || tp.modelId, created_at: tp.createdAt, error_message: s.error || '未知错误', data_source_name: tp.dataSourceName })
                resultMsg.value = `训练失败: ${s.error || '未知错误'}`
                loadHistory()
              }
            }
          } catch { /* retry */ }
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
      if (idx !== -1) taskProgresses.value.splice(idx, 1)
    }

    function addToHistory(item) {
      taskHistory.value.unshift(item)
      if (taskHistory.value.length > 20) taskHistory.value = taskHistory.value.slice(0, 20)
    }

    async function handleStopTask(tp) {
      try {
        const taskLabel = tp.taskType === 'train-and-predict' ? '训练+预测' : '训练'
        await ElMessageBox.confirm(`确认停止${taskLabel}任务 "${tp.taskId.slice(0, 12)}..." 吗？`, '确认停止',
          { confirmButtonText: '确认停止', cancelButtonText: '取消', type: 'warning' })
      } catch { return }
      try {
        const stopRes = await stopTrainTask(tp.taskId)
        ElMessage.success('任务已停止')
        const taskId = tp.taskId
        const modelId = (stopRes && stopRes.model_id) || tp.modelId
        removeFromActive(taskId)
        addToHistory({ status: 'failed', task_id: taskId, model_id: modelId, created_at: tp.createdAt, error_message: '用户手动停止', data_source_name: tp.dataSourceName })
        resultMsg.value = '任务已停止'
      } catch (e) { ElMessage.error(`停止任务失败: ${e.message || e}`) }
    }

    async function handleDeleteProgress(tp) {
      try {
        await ElMessageBox.confirm(`确认删除此进度记录吗？\n任务: ${tp.taskId.slice(0, 12)}...\n类型: ${tp.taskType === 'predict' ? '预测' : tp.taskType === 'train-and-predict' ? '训练+预测' : '训练'}\n状态: ${tp.status === 'running' ? '运行中(僵尸任务)' : tp.status === 'failed' ? '失败' : '成功'}`, '确认删除',
          { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' })
      } catch { return }
      try {
        await deleteForecastProgress(tp.taskId)
        const idx = taskProgresses.value.findIndex(p => p.taskId === tp.taskId)
        if (idx !== -1) taskProgresses.value.splice(idx, 1)
        ElMessage.success('已删除')
      } catch (e) { ElMessage.error(`删除失败: ${e.message || e}`) }
    }

    async function handleDeleteHistory(row) {
      const modelId = row.model_id
      const taskId = row.task_id
      if (!modelId && !taskId) { ElMessage.warning('该记录缺少标识信息，无法删除'); return }
      try {
        const label = modelId ? `模型 #${modelId}` : `任务 ${(taskId || '').slice(0, 12)}...`
        await ElMessageBox.confirm(`确认删除 ${label} 及相关预测记录吗？`, '确认删除',
          { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' })
      } catch { return }
      try {
        // 同时删除训练模型和预测历史，确保重新加载后不会残留
        if (modelId) await deleteTrainHistory(modelId)
        if (taskId) await deleteForecastProgress(taskId)
        ElMessage.success('删除成功')
      } catch (e) {
        ElMessage.error(`删除失败: ${e.message || e}`)
      }
      await loadHistory()
    }

    async function handleTrainAndPredict() {
      if (_trainAndPredictLock) return
      _trainAndPredictLock = true
      trainAndPredictLoading.value = true
      resultMsg.value = ''
      try {
        const tableName = form.value.tableName.trim() || null
        const res = await trainAndPredict(form.value.dataSourceId, form.value.trainDays, form.value.forecastDays, tableName)
        const taskId = res.task_id || (res.data && res.data.task_id)
        if (!taskId) { resultMsg.value = '任务提交失败'; return }
        const ds = dataSources.value.find(d => d.id === form.value.dataSourceId)
        const dsName = ds ? ds.name : `数据源#${form.value.dataSourceId}`
        taskProgresses.value.push({ taskId, percent: 0, phase: '初始化', detail: '训练+预测任务已提交', status: 'running', taskType: 'train-and-predict', createdAt: new Date().toLocaleString(), dataSourceName: dsName })
        startPolling()
        resultMsg.value = `训练+预测任务已提交，task_id=${taskId.slice(0, 16)}...`
      } catch (e) { resultMsg.value = `提交失败: ${e.message || e}` }
      finally { trainAndPredictLoading.value = false; _trainAndPredictLock = false }
    }

    onMounted(async () => {
      await loadDataSources()
      // 从 localStorage 恢复后，如果有已选数据源则加载预测数据
      if (form.value.dataSourceId) {
        // 预测结果已在独立页面展示
      }
      await loadHistory()
      checkRunningTasks()
    })

    onBeforeUnmount(() => { stopPolling() })

    async function checkRunningTasks() {
      try {
        const tasksRes = await getMyTrainTasks()
        const list = Array.isArray(tasksRes) ? tasksRes : (tasksRes.data || [])
        let hasRunning = false
        for (const t of list) {
          if (t.status === 'training' && t.task_id) {
            hasRunning = true
            const exists = taskProgresses.value.find(p => p.taskId === t.task_id)
            if (!exists) {
              const progress = t.progress || {}
              taskProgresses.value.push({ taskId: t.task_id, modelId: t.model_id, percent: progress.percent || 0, phase: progress.phase || '正在恢复', detail: progress.detail || '查询任务状态...', status: 'running', taskType: 'train', createdAt: t.created_at ? new Date(t.created_at).toLocaleString() : '', dataSourceName: t.data_source_name || '' })
            }
          } else if (t.status === 'ready' || t.status === 'failed') {
            // loadHistory 已处理
          }
        }
        // 查询执行中的预测任务
        try {
          const forecastRunningRes = await getForecastRunning()
          const forecastList = Array.isArray(forecastRunningRes) ? forecastRunningRes : (forecastRunningRes.data || [])
          for (const f of forecastList) {
            if (f.task_id) {
              hasRunning = true
              const exists = taskProgresses.value.find(p => p.taskId === f.task_id)
              if (!exists) {
                taskProgresses.value.push({ taskId: f.task_id, modelId: f.model_id, percent: f.percent || 0, phase: f.phase || '正在恢复', detail: f.detail || '预测任务恢复中...', status: 'running', taskType: 'predict', createdAt: '', dataSourceName: f.data_source_name || '' })
              }
            }
          }
        } catch { /* silent */ }
        if (hasRunning) { resultMsg.value = '检测到后台运行中的任务，正在恢复进度...'; startPolling() }
      } catch { /* silent */ }
    }

    return {
      form, dataSources, trainAndPredictLoading, loading, resultMsg, taskProgress,
      taskProgresses, taskHistory,
      handleTrainAndPredict, handleStopTask,
      handleDeleteProgress, handleDeleteHistory, onDataSourceChange,
    }
  }
}
</script>

<style scoped>
.sales-forecast { padding: 16px; }
.action-card { margin: 16px 0; }
.chart-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.progress-list { margin-bottom: 16px; }
.progress-card { margin-bottom: 12px; }
.progress-body { padding: 4px 0; }
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.progress-info { display: flex; justify-content: space-between; align-items: center; flex: 1; font-size: 14px; margin-right: 12px; }
.progress-actions { flex-shrink: 0; }
.progress-phase { color: var(--el-text-color-primary); font-weight: 500; }
.progress-percent { color: var(--el-text-color-secondary); }
.progress-detail { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.progress-time { margin-top: 4px; font-size: 11px; color: var(--el-text-color-placeholder); }
.history-card { margin-bottom: 16px; }
.model-option { padding: 2px 0; line-height: 1.5; }
.model-option-line1 { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.model-option-line2 { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--el-text-color-secondary); }
.model-option-id { font-weight: 600; color: var(--el-color-primary); min-width: 32px; }
.model-option-store { background: var(--el-fill-color-light); padding: 0 6px; border-radius: 4px; font-size: 12px; }
.model-option-metrics { color: var(--el-color-success); font-size: 12px; }
.model-option-rows { color: var(--el-color-warning); }
.model-option-time { margin-left: auto; }
.filter-bar { display: flex; align-items: center; gap: 8px; }
</style>
