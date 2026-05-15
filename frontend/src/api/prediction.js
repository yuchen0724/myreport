import request from '@/utils/request'

export function trainModel(dataSourceId, trainDays, tableName) {
  return request.post('/prediction/train', {
    data_source_id: dataSourceId,
    train_days: trainDays || null,
    table_name: tableName || null,
  })
}

export function runPredict(dataSourceId, forecastDays, tableName, modelId) {
  return request.post('/prediction/predict', {
    data_source_id: dataSourceId,
    forecast_days: forecastDays || null,
    table_name: tableName || null,
    model_id: modelId || null,
  })
}

export function getForecast(params) {
  return request.get('/prediction/forecast', { params })
}

export function getTrainStatus(taskId) {
  return request.get(`/prediction/train/status/${taskId}`)
}

export function getPredictStatus(taskId) {
  return request.get(`/prediction/predict/status/${taskId}`)
}

export function getMyTrainTasks(withProgress = true) {
  return request.get('/prediction/train/tasks', { params: { with_progress: withProgress, _t: Date.now() } })
}

export function stopTrainTask(taskId) {
  return request.post(`/prediction/train/${taskId}/stop`)
}

export function deleteTrainHistory(modelId) {
  return request.delete(`/prediction/train/${modelId}/history`)
}

export function deleteTrainHistoryByTask(taskId) {
  return request.delete(`/prediction/train/by-task/${taskId}/history`)
}

export function getReadyModels(dataSourceId) {
  return request.get('/prediction/train/tasks', {
    params: { with_progress: false, _t: Date.now() },
  }).then(res => {
    // 从 task 列表中筛选出 ready 且匹配数据源的
    const list = Array.isArray(res) ? res : (res.data || [])
    return list.filter(m => m.status === 'ready' && m.data_source_id === dataSourceId)
  })
}

export function getForecastHistory(params) {
  return request.get('/prediction/forecast/history', { params })
}

export function getForecastRunning() {
  return request.get('/prediction/forecast/running', { params: { _t: Date.now() } })
}

export function deleteForecastProgress(taskId) {
  return request.delete(`/prediction/forecast/progress/${taskId}`)
}

export function trainAndPredict(dataSourceId, trainDays, forecastDays, tableName) {
  return request.post('/prediction/train-and-predict', {
    data_source_id: dataSourceId,
    train_days: trainDays || null,
    forecast_days: forecastDays || null,
    table_name: tableName || null,
  })
}
