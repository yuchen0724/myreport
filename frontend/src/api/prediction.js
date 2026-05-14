import request from '@/utils/request'

export function trainModel(dataSourceId, trainDays, tableName) {
  return request.post('/prediction/train', {
    data_source_id: dataSourceId,
    train_days: trainDays || null,
    table_name: tableName || null,
  })
}

export function runPredict(dataSourceId, forecastDays, tableName) {
  return request.post('/prediction/predict', {
    data_source_id: dataSourceId,
    forecast_days: forecastDays || null,
    table_name: tableName || null,
  })
}

export function getForecast(params) {
  return request.get('/prediction/forecast', { params })
}

export function getTrainStatus(taskId) {
  return request.get(`/prediction/train/status/${taskId}`)
}

export function getMyTrainTasks() {
  return request.get('/prediction/train/tasks')
}
