<template>
  <div class="static-table-wrapper">
    <!-- 工具栏 -->
    <div class="table-toolbar" v-if="showToolbar">
      <el-popover placement="bottom-start" :width="220" trigger="click">
        <template #reference>
          <el-button size="small">
            <el-icon><Grid /></el-icon>
            列展示
          </el-button>
        </template>
        <div class="column-visibility">
          <el-checkbox
            v-model="checkAll"
            :indeterminate="isIndeterminate"
            @change="handleCheckAll"
          >全选</el-checkbox>
          <el-checkbox-group v-model="internalVisible" @change="handleCheckChange">
            <el-checkbox
              v-for="col in allColumnDefs"
              :key="col.prop"
              :label="col.prop"
              :value="col.prop"
            >{{ col.label }}</el-checkbox>
          </el-checkbox-group>
        </div>
      </el-popover>

      <!-- 搜索框 -->
      <el-input
        v-if="searchable"
        v-model="searchText"
        placeholder="搜索表格数据..."
        clearable
        size="small"
        style="width: 200px; margin-left: 10px"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <slot name="toolbar-extra" />
    </div>

    <!-- 数据表格 -->
    <el-table
      ref="tableRef"
      :data="filteredData"
      v-loading="loading"
      border
      stripe
      max-height="500"
      style="width: 100%"
      @header-dragend="handleHeaderDragEnd"
      v-bind="$attrs"
    >
      <el-table-column
        v-for="col in visibleColumnDefs"
        :key="col.prop"
        v-bind="col"
        :width="colWidths[col.prop] || col.width"
      >
        <template v-if="col.slotName" #default="{ row }">
          <slot :name="col.slotName" :row="row" />
        </template>
      </el-table-column>
      <slot />
    </el-table>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { Grid, Search } from '@element-plus/icons-vue'
import { useTableStorage } from '@/composables/useTableStorage'

const props = defineProps({
  columns: { type: Array, required: true },  // [{prop, label, width, slotName}]
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  tableId: { type: String, default: 'default' },
  showToolbar: { type: Boolean, default: true },
  searchable: { type: Boolean, default: true },
  showSearch: { type: Boolean, default: true },  // 兼容旧参数
})

const storage = useTableStorage(props.tableId)
const tableRef = ref(null)
const searchText = ref('')

// 列定义
const allColumnDefs = computed(() => props.columns)
const allProps = computed(() => allColumnDefs.value.map(c => c.prop))

// 列显隐
const internalVisible = ref([])
const visibleColumnDefs = ref([])

watch(allColumnDefs, (defs) => {
  if (!defs || defs.length === 0) return
  const saved = storage.loadColumnOrder()
  if (saved && saved.length > 0) {
    const valid = saved.filter(p => defs.some(c => c.prop === p))
    if (valid.length > 0) {
      internalVisible.value = valid
      syncVisibleDefs()
      return
    }
  }
  internalVisible.value = defs.map(c => c.prop)
  syncVisibleDefs()
}, { immediate: true })

function syncVisibleDefs() {
  const propsSet = new Set(internalVisible.value)
  visibleColumnDefs.value = allColumnDefs.value.filter(c => propsSet.has(c.prop))
}

const checkAll = computed(() => internalVisible.value.length === allColumnDefs.value.length)
const isIndeterminate = computed(() => {
  const len = internalVisible.value.length
  return len > 0 && len < allColumnDefs.value.length
})

function handleCheckAll(val) {
  internalVisible.value = val ? [...allProps.value] : []
  syncVisibleDefs()
  storage.saveColumnOrder(internalVisible.value)
}

function handleCheckChange() {
  syncVisibleDefs()
  storage.saveColumnOrder(internalVisible.value)
}

// 列宽
const colWidths = ref({})

onMounted(() => {
  // 恢复持久化列宽
  allColumnDefs.value.forEach(c => {
    const w = storage.loadColumnWidth(c.prop)
    if (w) colWidths.value[c.prop] = w
  })
})

function handleHeaderDragEnd(newWidth, oldWidth, column) {
  if (column && column.property) {
    colWidths.value[column.property] = newWidth
    storage.saveColumnWidth(column.property, newWidth)
  }
}

// 搜索
const filteredData = computed(() => {
  if (!searchText.value) return props.data
  const q = searchText.value.toLowerCase()
  return props.data.filter(row => {
    return allColumnDefs.value.some(col => {
      const v = row[col.prop]
      if (v === null || v === undefined) return false
      return String(v).toLowerCase().includes(q)
    })
  })
})
</script>

<style scoped>
.static-table-wrapper {
  width: 100%;
}
.table-toolbar {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.column-visibility {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
