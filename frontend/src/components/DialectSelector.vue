<template>
  <div class="dialect-selector" :class="{ 'is-small': size === 'small' }">
    <el-select
      v-model="selectedDialect"
      :placeholder="placeholder"
      :size="size"
      :style="{ width: width }"
      filterable
      clearable
      @change="handleChange"
    >
      <el-option
        label="自动检测"
        value=""
      >
        <span style="float: left">🤖 自动检测</span>
        <span style="float: right; color: #8492a6; font-size: 12px">default</span>
      </el-option>
      <el-option
        v-for="dialect in dialects"
        :key="dialect.name"
        :label="dialect.label"
        :value="dialect.name"
      >
        <span style="float: left">{{ getDialectIcon(dialect.name) }} {{ dialect.label }}</span>
        <span style="float: right; color: #8492a6; font-size: 12px">{{ dialect.name }}</span>
      </el-option>
    </el-select>

    <!-- 方言详情提示 -->
    <el-popover
      v-if="showDetail && currentDialect"
      placement="bottom"
      :width="350"
      trigger="hover"
    >
      <template #reference>
        <el-button
          :size="size"
          type="info"
          link
          class="detail-btn"
        >
          <el-icon><InfoFilled /></el-icon>
        </el-button>
      </template>
      <div class="dialect-detail">
        <h4 style="margin: 0 0 8px 0">{{ currentDialect.label }}</h4>
        <p style="color: #666; margin: 0 0 12px 0; font-size: 13px">{{ currentDialect.description }}</p>
        <div class="detail-features">
          <el-tag v-if="currentDialect.backtick_quoted" size="small" type="info">反引号 `标识符`</el-tag>
          <el-tag v-if="currentDialect.double_quote_quoted" size="small" type="info">双引号 "标识符"</el-tag>
          <el-tag v-if="currentDialect.allow_multistatement" size="small" type="warning">允许多语句</el-tag>
          <el-tag v-if="!currentDialect.require_select_start" size="small" type="success">不限 SELECT 开头</el-tag>
        </div>
        <div v-if="currentDialect.allowed_keywords && currentDialect.allowed_keywords.length" class="detail-section">
          <strong>扩展关键字：</strong>
          <span class="keyword-list">{{ currentDialect.allowed_keywords.slice(0, 10).join(', ') }}{{ currentDialect.allowed_keywords.length > 10 ? '...' : '' }}</span>
        </div>
        <div v-if="currentDialect.extra_functions && currentDialect.extra_functions.length" class="detail-section">
          <strong>扩展函数：</strong>
          <span class="keyword-list">{{ currentDialect.extra_functions.slice(0, 8).join(', ') }}{{ currentDialect.extra_functions.length > 8 ? '...' : '' }}</span>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { getDialects, getDialectDetail } from '@/api/dialect'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '选择 SQL 方言'
  },
  size: {
    type: String,
    default: 'default'
  },
  width: {
    type: String,
    default: '200px'
  },
  showDetail: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const dialects = ref([])
const selectedDialect = ref(props.modelValue)
const currentDialectDetail = ref(null)

// 计算当前选中的方言详情
const currentDialect = computed(() => {
  if (!selectedDialect.value) return null
  return currentDialectDetail.value
})

// 方言图标映射
const dialectIcons = {
  mysql: '🐬',
  postgresql: '🐘',
  hive: '🐝',
  clickhouse: '⚡',
  doris: '🌟'
}

function getDialectIcon(name) {
  return dialectIcons[name] || '📦'
}

// 加载方言列表
async function loadDialects() {
  try {
    dialects.value = await getDialects()
  } catch (error) {
    console.warn('加载 SQL 方言列表失败', error)
  }
}

// 加载方言详情
async function loadDialectDetail(name) {
  if (!name) {
    currentDialectDetail.value = null
    return
  }
  try {
    currentDialectDetail.value = await getDialectDetail(name)
  } catch (error) {
    console.warn('加载方言详情失败', error)
    currentDialectDetail.value = null
  }
}

// 处理选择变更
function handleChange(value) {
  emit('update:modelValue', value || '')
  emit('change', value || '')
  loadDialectDetail(value)
}

// 监听外部 v-model 变化
watch(() => props.modelValue, (val) => {
  if (val !== selectedDialect.value) {
    selectedDialect.value = val || ''
    loadDialectDetail(val)
  }
})

onMounted(() => {
  loadDialects()
  if (selectedDialect.value) {
    loadDialectDetail(selectedDialect.value)
  }
})
</script>

<style scoped>
.dialect-selector {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.detail-btn {
  margin-left: 4px;
}

.dialect-detail {
  font-size: 13px;
}

.detail-features {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.detail-section {
  margin-bottom: 6px;
  line-height: 1.6;
}

.detail-section strong {
  color: #333;
}

.keyword-list {
  color: #666;
  font-family: monospace;
  font-size: 12px;
}

.is-small .detail-btn {
  font-size: 12px;
}
</style>
