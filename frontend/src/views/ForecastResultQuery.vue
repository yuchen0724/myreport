<template>
  <div class="forecast-result-query">
    <el-card>
      <template #header>
        <span>预测结果查询</span>
      </template>

      <el-form :inline="true" label-width="90px">
        <el-row :gutter="16" style="width: 100%">
          <el-col :span="8">
            <el-form-item label="数据源">
              <el-select
                v-model="filters.dataSourceId"
                placeholder="请选择数据源"
                clearable
                filterable
                style="width: 100%"
                @change="onDataSourceChange"
              >
                <el-option
                  v-for="ds in dataSources"
                  :key="ds.id"
                  :label="ds.name"
                  :value="ds.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="模型">
              <el-select
                v-model="filters.modelId"
                placeholder="全部模型"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="m in models"
                  :key="m.model_id"
                  :label="`模型 #${m.model_id} (${formatDate(m.trained_at)})`"
                  :value="m.model_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="门店编码">
              <el-input
                v-model="filters.storeCode"
                placeholder="输入门店编码"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="width: 100%">
          <el-col :span="8">
            <el-form-item label="商品编码">
              <el-input
                v-model="filters.matnr"
                placeholder="输入商品编码"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预测日期">
              <el-date-picker
                v-model="filters.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="排序">
              <el-select v-model="filters.sortBy" style="width: 100%">
                <el-option label="预测日期" value="forecast_date" />
                <el-option label="预测值" value="predicted_value" />
                <el-option label="门店编码" value="store_code" />
                <el-option label="商品编码" value="matnr" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="方向">
              <el-select v-model="filters.sortOrder" style="width: 100%">
                <el-option label="升序" value="asc" />
                <el-option label="降序" value="desc" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row style="width: 100%; margin-top: 8px">
          <el-form-item>
            <el-button type="primary" @click="handleSearch" :loading="loading">
              查询
            </el-button>
            <el-button @click="handleReset">重置</el-button>
            <el-button
              type="success"
              @click="handleExport"
              :loading="exporting"
              :disabled="!hasData"
            >
              导出 Excel
            </el-button>
          </el-form-item>
        </el-row>
      </el-form>
    </el-card>

    <el-card style="margin-top: 16px">
      <div class="result-header">
        <span v-if="total > 0">共 {{ total }} 条记录</span>
        <span v-else>&nbsp;</span>
      </div>

      <el-table
        :data="forecastData"
        v-loading="loading"
        empty-text="暂无匹配的预测结果"
        border
        stripe
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="store_code" label="门店编码" width="120" show-overflow-tooltip />
        <el-table-column prop="matnr" label="商品编码" width="160" show-overflow-tooltip />
        <el-table-column prop="forecast_date" label="预测日期" width="130" />
        <el-table-column prop="predicted_value" label="预测值" width="140">
          <template #default="{ row }">
            {{ row.predicted_value.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="lower_bound" label="下限" width="140">
          <template #default="{ row }">
            {{ row.lower_bound != null ? row.lower_bound.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="upper_bound" label="上限" width="140">
          <template #default="{ row }">
            {{ row.upper_bound != null ? row.upper_bound.toFixed(2) : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          v-model:page-size="pageSize"
          v-model:current-page="page"
          :page-sizes="[20, 50, 100]"
          @current-change="loadForecast"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDataSourceList } from '@/api/data_source'
import { getForecast, getMyTrainTasks, exportForecastExcel } from '@/api/prediction'

const dataSources = ref([])
const models = ref([])
const loading = ref(false)
const exporting = ref(false)
const forecastData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  dataSourceId: null,
  modelId: null,
  storeCode: '',
  matnr: '',
  dateRange: null,
  sortBy: 'forecast_date',
  sortOrder: 'asc',
})

const hasData = computed(() => forecastData.value.length > 0)

function formatDate(iso) {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}

async function loadDataSources() {
  try {
    const res = await getDataSourceList()
    dataSources.value = Array.isArray(res) ? res : (res.data || [])
  } catch {
    ElMessage.error('加载数据源失败')
  }
}

async function loadModels() {
  if (!filters.dataSourceId) {
    models.value = []
    return
  }
  try {
    const res = await getMyTrainTasks(false)
    const list = Array.isArray(res) ? res : (res.data || [])
    models.value = list.filter(m => m.status === 'ready' && m.data_source_id === filters.dataSourceId)
    // 如果当前选中的模型不在新列表中，清空
    if (filters.modelId && !models.value.some(m => m.model_id === filters.modelId)) {
      filters.modelId = null
    }
  } catch {
    models.value = []
  }
}

function onDataSourceChange() {
  filters.modelId = null
  loadModels()
}

function buildParams() {
  const params = {
    data_source_id: filters.dataSourceId,
    page: page.value,
    page_size: pageSize.value,
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
  }
  if (filters.modelId) params.model_id = filters.modelId
  if (filters.storeCode) params.store_code = filters.storeCode.trim()
  if (filters.matnr) params.matnr = filters.matnr.trim()
  if (filters.dateRange && filters.dateRange.length === 2) {
    params.start_date = filters.dateRange[0]
    params.end_date = filters.dateRange[1]
  }
  return params
}

async function loadForecast() {
  if (!filters.dataSourceId) {
    ElMessage.warning('请先选择数据源')
    return
  }
  loading.value = true
  try {
    const res = await getForecast(buildParams())
    const data = res?.items || res?.data?.items || []
    forecastData.value = data
    total.value = res?.total ?? 0
  } catch (e) {
    ElMessage.error('查询失败: ' + (e.message || '未知错误'))
    forecastData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadForecast()
}

function handleReset() {
  filters.dataSourceId = null
  filters.modelId = null
  filters.storeCode = ''
  filters.matnr = ''
  filters.dateRange = null
  filters.sortBy = 'forecast_date'
  filters.sortOrder = 'asc'
  page.value = 1
  pageSize.value = 20
  forecastData.value = []
  total.value = 0
  models.value = []
}

function onSizeChange() {
  page.value = 1
  loadForecast()
}

function handleSortChange({ prop, order }) {
  if (prop) {
    filters.sortBy = prop
    filters.sortOrder = order === 'descending' ? 'desc' : 'asc'
    handleSearch()
  }
}

async function handleExport() {
  if (!filters.dataSourceId) {
    ElMessage.warning('请先选择数据源')
    return
  }
  exporting.value = true
  try {
    const params = {
      data_source_id: filters.dataSourceId,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
    }
    if (filters.modelId) params.model_id = filters.modelId
    if (filters.storeCode) params.store_code = filters.storeCode.trim()
    if (filters.matnr) params.matnr = filters.matnr.trim()
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }

    const blob = await exportForecastExcel(params)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `预测结果_${Date.now()}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败: ' + (e.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadDataSources()
})
</script>

<style scoped>
.forecast-result-query {
  padding: 20px;
}

.result-header {
  margin-bottom: 12px;
  font-size: 14px;
  color: #606266;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
