<template>
  <div class="enhanced-table-wrapper">
    <!-- 工具栏 -->
    <div v-if="showToolbar && visibleColumns.length > 0" class="table-toolbar">
      <TableToolbar
        :all-columns="columns || []"
        v-model="enhancer.visibleColumns.value"
        v-model:search-text="searchText"
        :enable-expand="enableExpandFn"
        :expanded="enhancer.showExpand.value"
        @toggle-expand="enhancer.toggleExpand"
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
      :summary-method="showSummary ? enhancer.handleSummary : undefined"
      :max-height="maxHeight"
      :height="height"
      style="width: 100%"
      @header-dragend="enhancer.handleHeaderDragEnd"
      v-bind="$attrs"
    >
      <!-- 行展开列 (dynamic mode) -->
      <el-table-column v-if="showExpandFn" type="expand">
        <template #default="{ row }">
          <div class="expand-detail">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item
                v-for="(val, key) in row"
                :key="key"
                :label="key"
              >
                {{ val !== null && val !== undefined ? val : '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </template>
      </el-table-column>

      <!-- 动态列 (dynamic mode) -->
      <el-table-column
        v-for="col in dynamicColumns"
        :key="col"
        :prop="col"
        :label="col"
        :width="enhancer.storage.loadColumnWidth(col) || undefined"
        :fixed="enhancer.storage.loadFixedColumn(col) || false"
        min-width="80"
        show-overflow-tooltip
        sortable="custom"
      >
        <template #header>
          <div class="column-header-with-actions">
            <span>{{ col }}</span>
            <el-dropdown trigger="click" size="small" @command="(cmd) => enhancer.handleColumnAction(cmd, col)">
              <el-button size="small" circle :icon="MoreFilled" class="col-action-btn" />
              <template #dropdown>
                <el-dropdown-menu v-if="fixable">
                  <el-dropdown-item command="fixed-left" :disabled="enhancer.isFixedLeft(col)">
                    固定到左侧
                  </el-dropdown-item>
                  <el-dropdown-item command="fixed-right" :disabled="enhancer.isFixedRight(col)">
                    固定到右侧
                  </el-dropdown-item>
                  <el-dropdown-item command="clear-fixed" :disabled="!enhancer.isAnyFixed(col)">
                    取消固定
                  </el-dropdown-item>
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

      <!-- 默认插槽：额外固定列（如操作列） -->
      <slot />
    </el-table>
  </div>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import TableToolbar from '@/components/TableToolbar.vue'
import { useTableEnhancer } from '@/composables/useTableEnhancer'

const props = defineProps({
  // 数据相关
  data: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },

  // 表格增强开关
  showToolbar: { type: Boolean, default: true },
  enableColumnDrag: { type: Boolean, default: true },
  fixable: { type: Boolean, default: true },
  summarizable: { type: Boolean, default: true },
  enableExpand: { type: Boolean, default: true },
  searchable: { type: Boolean, default: true },
  expandThreshold: { type: Number, default: 6 },

  // 尺寸
  maxHeight: { type: [Number, String], default: 500 },
  height: { type: [Number, String], default: undefined },

  // Storage key
  tableId: { type: String, default: 'default' },
})

const emit = defineEmits(['re-query'])

// useTableEnhancer 内部创建的 columns ref
// 如果用户未传 columns 或 columns 为空，从 data[0] 自动推导
const columnsRef = computed(() => {
  if (props.columns && props.columns.length > 0) return props.columns
  if (props.data && props.data.length > 0) {
    return Object.keys(props.data[0])
  }
  return []
})

const enhancer = useTableEnhancer({
  mode: 'dynamic',
  tableId: props.tableId,
  columns: columnsRef,
  enableColumnDrag: props.enableColumnDrag,
  enableColumnFix: props.fixable,
  enableSummary: props.summarizable,
  enableExpand: props.enableExpand,
  enableSearch: props.searchable,
  expandThreshold: props.expandThreshold,
})

const dynamicColumns = computed(() => enhancer.visibleColumns.value)
const showExpandFn = computed(() => enhancer.showExpand.value)
const enableExpandFn = computed(() => props.enableExpand && props.columns.length > props.expandThreshold)
const showSummary = computed(() => props.summarizable && enhancer.storage.loadSummaryConfig())

// 搜索过滤
const searchText = enhancer.searchText
const filteredData = computed(() => {
  if (!searchText.value) return props.data
  const q = searchText.value.toLowerCase()
  return props.data.filter(row => {
    return Object.values(row).some(v => {
      if (v === null || v === undefined) return false
      return String(v).toLowerCase().includes(q)
    })
  })
})

const tableRef = enhancer.tableRef

onBeforeUnmount(() => {
  enhancer.destroy()
})
</script>

<style scoped>
.enhanced-table-wrapper {
  width: 100%;
}
.table-toolbar {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.column-header-with-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}
.col-action-btn {
  opacity: 0.4;
  transition: opacity 0.15s;
}
:deep(.el-table__header-wrapper) .col-action-btn:hover {
  opacity: 1;
}
.expand-detail {
  padding: 12px;
}
</style>
