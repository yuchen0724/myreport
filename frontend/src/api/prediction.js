import request from '@/utils/request'

export function trainModel(dataSourceId, trainDays) {
  return request.post('/prediction/train', {
    data_source_id: dataSourceId,
    train_days: trainDays || null,
  })
}

export function runPredict(dataSourceId, forecastDays) {
  return request.post('/prediction/predict', {
    data_source_id: dataSourceId,
    forecast_days: forecastDays || null,
  })
}

export function getForecast(params) {
  return request.get('/prediction/forecast', { params })
}
