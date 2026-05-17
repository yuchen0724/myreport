<template>
  <div class="table-toolbar">
    <!-- 列显隐控制 -->
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
        >
          全选
        </el-checkbox>
        <el-checkbox-group v-model="internalVisible" @change="handleCheckChange">
          <el-checkbox
            v-for="col in allColumns"
            :key="col.key || col"
            :label="col.key || col"
            :value="col.key || col"
          >
            {{ col.label || col }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
    </el-popover>

    <!-- 搜索框 -->
    <el-input
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

const props = defineProps({
  allColumns: { type: Array, required: true },
  modelValue: { type: Array, required: true },
  enableExpand: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'update:searchText', 'toggle-expand'])

const searchText = ref('')
watch(searchText, (val) => emit('update:searchText', val))

const internalVisible = ref([...props.modelValue])
watch(() => props.modelValue, (val) => {
  internalVisible.value = [...val]
})

const checkAll = computed(() => internalVisible.value.length === props.allColumns.length)
const isIndeterminate = computed(() => {
  const len = internalVisible.value.length
  return len > 0 && len < props.allColumns.length
})

function handleCheckAll(val) {
  const all = props.allColumns.map(c => c.key || c)
  emit('update:modelValue', val ? all : [])
}

function handleCheckChange(value) {
  emit('update:modelValue', [...value])
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
  gap: 8px;
}
</style>
