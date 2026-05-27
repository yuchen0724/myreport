<template>
  <div class="drilldown-panel" v-if="visible">
    <div class="drilldown-header">
      <div class="drilldown-title">
        <el-icon><DataLine /></el-icon>
        <span>{{ title || '下钻明细' }}</span>
      </div>
      <div class="drilldown-actions">
        <el-button size="small" text @click="exportData" :disabled="!tableData.rows.length">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <el-button size="small" text @click="$emit('close')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="drilldown-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 错误 -->
    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      @close="error = ''"
      class="drilldown-error"
    />

    <!-- 数据表格 -->
    <div v-else class="drilldown-table-wrapper">
      <el-table
        :data="tableData.rows"
        border
        stripe
        size="small"
        max-height="400"
        style="width: 100%"
        empty-description="暂无数据"
      >
        <el-table-column
          v-for="(col, idx) in tableData.columns"
          :key="idx"
          :prop="String(idx)"
          :label="col"
          min-width="120"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            {{ formatCell(row[idx]) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="drilldown-footer">
        <span class="drilldown-info">
          共 {{ tableData.total }} 条 · 耗时 {{ executionTime }}ms
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { DataLine, Download, Close } from '@element-plus/icons-vue'
import { executeDrilldown } from '@/api/dashboard'

const props = defineProps({
  visible: { type: Boolean, default: false },
  widgetId: { type: Number, default: null },
  templateId: { type: Number, default: null },
  clickData: { type: Object, default: () => ({}) },
  params: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close'])

const loading = ref(false)
const error = ref('')
const title = ref('')
const executionTime = ref(0)
const tableData = ref({ columns: [], rows: [], total: 0 })

// 监听 visible 变化，自动加载数据
watch(
  () => [props.visible, props.widgetId, props.templateId, props.clickData],
  ([visible, widgetId, templateId, clickData]) => {
    if (visible && widgetId && templateId && clickData && clickData.value !== undefined) {
      loadDrilldownData()
    }
  },
  { deep: true }
)

async function loadDrilldownData() {
  if (!props.widgetId || !props.templateId || !props.clickData) return

  loading.value = true
  error.value = ''
  tableData.value = { columns: [], rows: [], total: 0 }

  try {
    const res = await executeDrilldown({
      widget_id: props.widgetId,
      template_id: props.templateId,
      click_data: {
        field: props.clickData.field || 'category',
        value: props.clickData.value,
        label: props.clickData.label,
      },
      params: props.params,
    })

    const data = res.data || res
    tableData.value = {
      columns: data.columns || [],
      rows: data.rows || [],
      total: data.total || 0,
    }
    executionTime.value = data.execution_time_ms || 0
    title.value = data.title || ''
  } catch (e) {
    console.error('钻取查询失败:', e)
    error.value = e?.response?.data?.message || e?.response?.data?.detail || e?.message || '钻取查询失败'
  } finally {
    loading.value = false
  }
}

function formatCell(val) {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') {
    return val.toLocaleString()
  }
  return String(val)
}

function exportData() {
  if (!tableData.value.rows.length) return

  // 生成 CSV
  const header = tableData.value.columns.join(',')
  const rows = tableData.value.rows.map(row =>
    row.map(cell => {
      const val = cell === null || cell === undefined ? '' : String(cell)
      // CSV 转义
      if (val.includes(',') || val.includes('"') || val.includes('\n')) {
        return `"${val.replace(/"/g, '""')}"`
      }
      return val
    }).join(',')
  )
  const csv = [header, ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `drilldown_${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.drilldown-panel {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  margin-top: 12px;
  overflow: hidden;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.drilldown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.drilldown-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.drilldown-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.drilldown-loading {
  padding: 20px;
}

.drilldown-error {
  margin: 12px;
}

.drilldown-table-wrapper {
  padding: 0;
}

.drilldown-footer {
  display: flex;
  justify-content: flex-end;
  padding: 8px 16px;
  background: #fafafa;
  border-top: 1px solid #f0f0f0;
}

.drilldown-info {
  font-size: 12px;
  color: #909399;
}
</style>
