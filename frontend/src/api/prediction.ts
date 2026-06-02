import request from "@/utils/request"

export interface PredictionTask {
  id: number
  task_id: string
  data_source_id: number
  model_type: string
  status: string
  progress: number
  created_by: number
  created_at: string
}

export interface ForecastResult {
  forecast_date: string
  predicted_value: number
  store_code?: string
  matnr?: string
}

// ── Training ──────────────────────────────────────────────

export function trainModel(
  dataSourceId: number,
  trainDays?: number | null,
  tableName?: string | null,
  modelType?: string
): Promise<PredictionTask> {
  return request.post("/prediction/train", {
    data_source_id: dataSourceId,
    model_type: modelType || "lightgbm",
    train_days: trainDays ?? null,
    table_name: tableName ?? null,
  }) as Promise<PredictionTask>
}

export function getTrainStatus(taskId: string): Promise<PredictionTask> {
  return request.get(`/prediction/train/status/${taskId}`)
}

export function getMyTrainTasks(withProgress = true): Promise<PredictionTask[]> {
  return request.get("/prediction/train/tasks", {
    params: { with_progress: withProgress, _t: Date.now() }
  })
}

export function stopTrainTask(taskId: string): Promise<void> {
  return request.post(`/prediction/train/${taskId}/stop`)
}

export function deleteTrainHistory(modelId: number): Promise<void> {
  return request.delete(`/prediction/history/${modelId}`)
}

export function deleteTrainHistoryByTask(taskId: string): Promise<void> {
  return request.delete(`/prediction/train/by-task/${taskId}/history`)
}

export function getReadyModels(dataSourceId: number): Promise<PredictionTask[]> {
  return request.get("/prediction/train/tasks", {
    params: { status: "ready", data_source_id: dataSourceId, with_progress: false, _t: Date.now() }
  }).then((res: unknown) => {
    const list = Array.isArray(res) ? res : ((res as Record<string, unknown>).data || [])
    return list as PredictionTask[]
  })
}

// ── Prediction ────────────────────────────────────────────

export function runPredict(
  dataSourceId: number,
  forecastDays?: number | null,
  tableName?: string | null,
  modelId?: number | null
): Promise<{ task_id: string }> {
  return request.post("/prediction/predict", {
    data_source_id: dataSourceId,
    forecast_days: forecastDays ?? null,
    table_name: tableName ?? null,
    model_id: modelId ?? null,
  }) as Promise<{ task_id: string }>
}

export function getPredictStatus(taskId: string): Promise<PredictionTask> {
  return request.get(`/prediction/predict/status/${taskId}`)
}

export function getForecast(params: Record<string, unknown>): Promise<ForecastResult[]> {
  return request.get("/prediction/forecast", { params }) as Promise<ForecastResult[]>
}

export function getForecastHistory(params: Record<string, unknown>): Promise<PredictionTask[]> {
  return request.get("/prediction/forecast/history", { params })
}

export function getForecastRunning(): Promise<PredictionTask[]> {
  return request.get("/prediction/forecast/running", { params: { _t: Date.now() } })
}

export function deleteForecastProgress(taskId: string): Promise<void> {
  return request.delete(`/prediction/forecast/progress/${taskId}`)
}

export function exportForecastExcel(params: Record<string, unknown>): Promise<Blob> {
  return request.post("/prediction/forecast/export", params, { responseType: "blob" })
}

// ── Algorithm ─────────────────────────────────────────────

export function recommendAlgorithm(dataSourceId: number, tableName?: string): Promise<{ algorithm: string }> {
  return request.get("/prediction/recommend-algorithm", {
    params: { data_source_id: dataSourceId, table_name: tableName ?? undefined, _t: Date.now() }
  })
}

// ── Combined ──────────────────────────────────────────────

export function trainAndPredict(
  dataSourceId: number,
  trainDays?: number | null,
  forecastDays?: number | null,
  tableName?: string | null,
  batchSize?: number | null,
  batchUnit?: string | null,
  testDays?: number | null,
  validDays?: number | null,
  modelType?: string | null,
): Promise<PredictionTask> {
  return request.post("/prediction/train-and-predict", {
    data_source_id: dataSourceId,
    model_type: modelType || "lightgbm",
    train_days: trainDays ?? null,
    test_days: testDays ?? null,
    valid_days: validDays ?? null,
    forecast_days: forecastDays ?? null,
    table_name: tableName ?? null,
    batch_size: batchSize ?? null,
    batch_unit: batchUnit ?? null,
  }) as Promise<PredictionTask>
}
