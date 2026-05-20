<template>
  <div class="table-toolbar">
    <!-- 列显隐 + 排序控制 -->
    <el-popover placement="bottom-start" :width="260" trigger="click">
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
        >
          全选
        </el-checkbox>
        <el-divider style="margin: 6px 0" />
        <div class="column-drag-hint">拖拽调整列顺序</div>
        <draggable
          v-model="internalColumns"
          item-key="key"
          handle=".drag-handle"
          animation="200"
          @end="onDragEnd"
        >
          <template #item="{ element }">
            <div class="column-item">
              <el-icon class="drag-handle"><Rank /></el-icon>
              <el-checkbox
                :model-value="internalVisible.includes(element.key)"
                @change="(val) => toggleColumn(element.key, val)"
              >
                {{ element.label }}
              </el-checkbox>
            </div>
          </template>
        </draggable>
      </div>
    </el-popover>

    <!-- 搜索框 -->
    <el-input
      v-if="showSearch"
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

    <!-- 行展开切换 -->
    <el-button
      v-if="enableExpand"
      size="small"
      :type="expanded ? 'primary' : 'default'"
      @click="$emit('toggle-expand')"
      style="margin-left: 10px"
    >
      <el-icon><Rank /></el-icon>
      行展开
    </el-button>

    <slot />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Grid, Search, Rank } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'

const props = defineProps({
  allColumns: { type: Array, required: true },
  modelValue: { type: Array, required: true },
  enableExpand: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
  showSearch: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'update:searchText', 'toggle-expand'])

const searchText = ref('')
watch(searchText, (val) => emit('update:searchText', val))

// 内部列列表：{ key, label } 格式，支持拖拽排序
const internalColumns = ref([])

function normalizeColumns(cols) {
  return cols.map(c => {
    if (typeof c === 'string') return { key: c, label: c }
    return { key: c.key || c, label: c.label || c.key || c }
  })
}

watch(() => props.allColumns, (cols) => {
  internalColumns.value = normalizeColumns(cols)
}, { immediate: true })

// 显隐状态
const internalVisible = ref([...props.modelValue])
watch(() => props.modelValue, (val) => {
  internalVisible.value = [...val]
})

const checkAll = computed(() => internalVisible.value.length === internalColumns.value.length)
const isIndeterminate = computed(() => {
  const len = internalVisible.value.length
  return len > 0 && len < internalColumns.value.length
})

function handleCheckAll(val) {
  const all = internalColumns.value.map(c => c.key)
  internalVisible.value = val ? [...all] : []
  emitUpdate()
}

function toggleColumn(key, visible) {
  if (visible) {
    if (!internalVisible.value.includes(key)) {
      internalVisible.value.push(key)
    }
  } else {
    internalVisible.value = internalVisible.value.filter(k => k !== key)
  }
  emitUpdate()
}

function onDragEnd() {
  emitUpdate()
}

function emitUpdate() {
  // 按 internalColumns 顺序，过滤出 visible 的列
  const ordered = internalColumns.value
    .map(c => c.key)
    .filter(k => internalVisible.value.includes(k))
  emit('update:modelValue', ordered)
}
</script>

<style scoped>
.table-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.column-visibility {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.column-drag-hint {
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}
.column-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
}
.drag-handle {
  cursor: grab;
  color: #c0c4cc;
  font-size: 14px;
}
.drag-handle:hover {
  color: #409eff;
}
.column-item:has(.drag-handle:active) {
  background: #f5f7fa;
  border-radius: 4px;
}
</style>
