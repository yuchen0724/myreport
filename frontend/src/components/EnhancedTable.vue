<template>
  <div class="enhanced-table-wrapper">
    <!-- 工具栏 -->
    <div v-if="showToolbar && dynamicColumns.length > 0" class="table-toolbar">
      <TableToolbar
        :all-columns="dynamicColumns"
        v-model="columnVisibility"
        v-model:search-text="searchText"
        :enable-expand="enableExpandFn"
        :expanded="expanded"
        @toggle-expand="toggleExpand"
        :show-search="searchable"
      >
        <slot name="toolbar-extra" />
      </TableToolbar>
    </div>

    <!-- 数据表格 -->
    <el-table
      ref="tableRef"
      :data="filteredData"
      v-loading="loading"
      border
      stripe
      :show-summary="showSummary"
      :summary-method="showSummary ? handleSummary : undefined"
      :max-height="maxHeight"
      :height="height"
      style="width: 100%"
      @header-dragend="handleHeaderDragEnd"
      v-bind="$attrs"
    >
      <!-- 行展开列 -->
      <el-table-column v-if="enableExpand && dynamicColumns.length > expandThreshold" type="expand">
        <template #default="{ row }">
          <div class="expand-detail">
              <el-descriptions :column="2" border size="small" style="max-width: 800px">
                <el-descriptions-item v-for="col in derivedColumns" :key="col" :label="expandLabel(col)" :span="1">
                  <template v-if="col === 'predicted_value' || col === 'lower_bound' || col === 'upper_bound'">
                    {{ row[col] != null ? Number(row[col]).toFixed(2) : '-' }}
                </template>
                <template v-else>
                  {{ row[col] !== null && row[col] !== undefined ? row[col] : '-' }}
                </template>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </template>
      </el-table-column>

      <!-- 动态列 -->
      <el-table-column
        v-for="col in dynamicColumns"
        :key="col"
        :prop="col"
        :label="getColumnLabel(col)"
        :width="storage.loadColumnWidth(col) || undefined"
        :fixed="storage.loadFixedColumn(col) || false"
        min-width="80"
        show-overflow-tooltip
        sortable="custom"
      >
        <template #header>
          <div class="column-header-with-actions">
            <span>{{ col }}</span>
            <el-dropdown trigger="click" size="small" @command="(cmd) => handleColumnAction(cmd, col)">
              <el-button size="small" circle :icon="MoreFilled" class="col-action-btn" />
              <template #dropdown>
                <el-dropdown-menu v-if="fixable">
                  <el-dropdown-item command="fixed-left" :disabled="isFixedLeft(col)">固定到左侧</el-dropdown-item>
                  <el-dropdown-item command="fixed-right" :disabled="isFixedRight(col)">固定到右侧</el-dropdown-item>
                  <el-dropdown-item command="clear-fixed" :disabled="!isAnyFixed(col)">取消固定</el-dropdown-item>
                </el-dropdown-menu>
                <el-dropdown-menu v-if="summarizable">
                  <el-dropdown-item divided command="summary-sum">汇总：求和</el-dropdown-item>
                  <el-dropdown-item command="summary-avg">汇总：平均数</el-dropdown-item>
                  <el-dropdown-item command="summary-min">汇总：最小值</el-dropdown-item>
                  <el-dropdown-item command="summary-max">汇总：最大值</el-dropdown-item>
                  <el-dropdown-item command="summary-count">汇总：计数</el-dropdown-item>
                  <el-dropdown-item divided command="clear-summary">清除汇总</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
        <template #default="{ row }">
          <slot :name="'cell-' + col" :row="row" :value="row[col]">
            {{ row[col] !== null && row[col] !== undefined ? row[col] : '-' }}
          </slot>
        </template>
      </el-table-column>

      <!-- 默认插槽：额外固定列 -->
      <slot />
    </el-table>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import TableToolbar from '@/components/TableToolbar.vue'
import { useTableStorage } from '@/composables/useTableStorage'

const props = defineProps({
  data: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  showToolbar: { type: Boolean, default: true },
  enableColumnDrag: { type: Boolean, default: true },
  fixable: { type: Boolean, default: true },
  summarizable: { type: Boolean, default: true },
  enableExpand: { type: Boolean, default: true },
  searchable: { type: Boolean, default: true },
  expandThreshold: { type: Number, default: 6 },
  maxHeight: { type: [Number, String], default: 500 },
  height: { type: [Number, String], default: undefined },
  tableId: { type: String, default: 'default' },
  columnLabels: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['re-query'])

const storage = useTableStorage(props.tableId)

// 行展开时字段名→中文映射
const FIELD_LABEL_MAP = {
  id: 'ID',
  store_code: '门店编码',
  matnr: '商品编码',
  forecast_date: '预测日期',
  predicted_value: '预测值',
  lower_bound: '置信下限',
  upper_bound: '置信上限',
  created_at: '创建时间',
  updated_at: '更新时间',
  deleted_at: '删除时间',
  status: '状态',
  model_id: '模型ID',
  task_id: '任务ID',
  data_source_id: '数据源ID',
  data_source_name: '数据源',
  error_message: '错误信息',
  result_count: '结果数量',
  forecast_days: '预测天数',
  sorted_date: '日期',
  store_name: '门店名称',
  matnr_name: '商品名称',
}

function expandLabel(key) {
  return props.columnLabels[key] || FIELD_LABEL_MAP[key] || key
}

function getColumnLabel(key) {
  return props.columnLabels[key] || FIELD_LABEL_MAP[key] || key
}

// 列名推导：优先 props.columns，其次从 data[0] 自动推导
const derivedColumns = computed(() => {
  if (props.columns && props.columns.length > 0) return props.columns
  if (props.data && props.data.length > 0) {
    const keys = Object.keys(props.data[0])
    console.log('[EnhancedTable] derivedColumns from data:', keys)
    return keys
  }
  console.log('[EnhancedTable] derivedColumns: empty, data.length=', props.data?.length, 'columns.length=', props.columns?.length)
  return []
})

// 列显隐状态
const columnVisibility = ref([])

// 动态列列表（取显隐过滤 + 持久化顺序）
const dynamicColumns = computed(() => {
  const all = derivedColumns.value
  if (!all || all.length === 0) return []

  // 第一次：用所有列初始化 visibility
  if (columnVisibility.value.length !== all.length) {
    const saved = storage.loadColumnOrder()
    if (saved && saved.length > 0) {
      const valid = saved.filter(c => all.includes(c))
      if (valid.length > 0) {
        columnVisibility.value = valid
        return valid
      }
    }
    columnVisibility.value = [...all]
    return [...all]
  }

  // 后续：按 visibility 顺序显示
  return columnVisibility.value.filter(c => all.includes(c))
})

// 搜索
const searchText = ref('')
const filteredData = computed(() => {
  if (!searchText.value) return props.data
  const q = searchText.value.toLowerCase()
  return props.data.filter(row =>
    Object.values(row).some(v => v != null && String(v).toLowerCase().includes(q))
  )
})

// 展开
const expanded = ref(false)
function toggleExpand() { expanded.value = !expanded.value }
const enableExpandFn = computed(() => props.enableExpand && dynamicColumns.value.length > props.expandThreshold)

// 汇总
const showSummary = computed(() => props.summarizable && storage.loadSummaryConfig())
function handleSummary({ columns: cols, data: rows }) {
  if (!props.summarizable) return []
  const config = storage.loadSummaryConfig()
  if (!config || Object.keys(config).length === 0) return []
  const labels = { sum: '合计', avg: '平均', min: '最小', max: '最大', count: '计数' }
  return cols.map(col => {
    const summary = config[col.property]
    if (!summary) return ''
    const vals = rows.map(r => Number(r[col.property])).filter(v => !isNaN(v))
    if (vals.length === 0) return ''
    let result
    switch (summary) {
      case 'sum': result = vals.reduce((a, b) => a + b, 0); break
      case 'avg': result = vals.reduce((a, b) => a + b, 0) / vals.length; break
      case 'min': result = Math.min(...vals); break
      case 'max': result = Math.max(...vals); break
      case 'count': result = vals.length; break
      default: return ''
    }
    return `${labels[summary]}: ${Number.isInteger(result) ? result : result.toFixed(2)}`
  })
}

// 列固定状态
function isFixedLeft(col) { return storage.loadFixedColumn(col) === 'left' }
function isFixedRight(col) { return storage.loadFixedColumn(col) === 'right' }
function isAnyFixed(col) { return !!storage.loadFixedColumn(col) }

// 列操作
function handleColumnAction(cmd, col) {
  if (cmd === 'fixed-left') storage.saveFixedColumn(col, 'left')
  else if (cmd === 'fixed-right') storage.saveFixedColumn(col, 'right')
  else if (cmd === 'clear-fixed') storage.saveFixedColumn(col, false)
  else if (cmd.startsWith('summary-') && props.summarizable) {
    const type = cmd.replace('summary-', '')
    const sc = storage.loadSummaryConfig() || {}
    storage.saveSummaryConfig({ ...sc, [col]: type })
  } else if (cmd === 'clear-summary' && props.summarizable) {
    const sc = storage.loadSummaryConfig() || {}
    if (sc[col]) { delete sc[col]; storage.saveSummaryConfig(sc) }
  }
}

// 列宽拖拽持久化
function handleHeaderDragEnd(newWidth, oldWidth, column) {
  if (column && column.property) {
    storage.saveColumnWidth(column.property, newWidth)
  }
}
</script>

<style scoped>
.enhanced-table-wrapper { width: 100%; }
.table-toolbar { margin-bottom: 8px; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.column-header-with-actions { display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.col-action-btn { opacity: 0.4; transition: opacity 0.15s; }
:deep(.el-table__header-wrapper) .col-action-btn:hover { opacity: 1; }
.expand-detail { padding: 12px; }
</style>
