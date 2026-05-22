import request from '@/utils/request'

export function trainModel(dataSourceId, trainDays, tableName, modelType) {
  return request.post('/prediction/train', {
    data_source_id: dataSourceId,
    model_type: modelType || 'lightgbm',
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
  return request.delete(`/prediction/history/${modelId}`)
}

export function deleteTrainHistoryByTask(taskId) {
  return request.delete(`/prediction/train/by-task/${taskId}/history`)
}

export function getReadyModels(dataSourceId) {
  return request.get('/prediction/train/tasks', {
    params: { 
      status: 'ready',  // 后端过滤：只返回 ready 状态
      data_source_id: dataSourceId,  // 后端过滤：只返回指定数据源
      with_progress: false, 
      _t: Date.now() 
    },
  }).then(res => {
    // 后端已过滤，前端只需简单返回
    const list = Array.isArray(res) ? res : (res.data || [])
    return list
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

export function exportForecastExcel(params) {
  return request.post('/prediction/forecast/export', params, { responseType: 'blob' })
}

export function trainAndPredict(dataSourceId, trainDays, forecastDays, tableName, batchSize, batchUnit, testDays, validDays, modelType) {
  return request.post('/prediction/train-and-predict', {
    data_source_id: dataSourceId,
    model_type: modelType || 'lightgbm',
    train_days: trainDays || null,
    test_days: testDays || null,
    valid_days: validDays || null,
    forecast_days: forecastDays || null,
    table_name: tableName || null,
    batch_size: batchSize || null,
    batch_unit: batchUnit || null,
  })
}
