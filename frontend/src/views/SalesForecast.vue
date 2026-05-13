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

    <!-- 训练结果显示 -->
    <el-alert
      v-if="trainResult"
      :title="trainResult"
      :type="trainResult.includes('成功') ? 'success' : 'error'"
      show-icon
      closable
      style="margin-bottom: 16px"
    />

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
import { trainModel, runPredict, getForecast } from '@/api/prediction'
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
    })
    const dataSources = ref([])
    const training = ref(false)
    const predicting = ref(false)
    const loading = ref(false)
    const trainResult = ref('')
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
      training.value = true
      trainResult.value = ''
      try {
        const res = await trainModel(form.value.dataSourceId, form.value.trainDays)
        trainResult.value = '模型训练成功！'
      } catch (e) {
        trainResult.value = `训练失败: ${e.message || e}`
      } finally { training.value = false }
    }

    async function handlePredict() {
      predicting.value = true
      trainResult.value = ''
      try {
        const res = await runPredict(form.value.dataSourceId, form.value.forecastDays)
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
    })

    return {
      form, dataSources, training, predicting, loading, trainResult,
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
</style>
