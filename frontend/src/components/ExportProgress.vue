<!-- frontend/src/components/ExportProgress.vue -->
<template>
  <div class="export-progress">
    <el-progress
      :percentage="progress"
      :status="status"
      :stroke-width="20"
    >
      <template #default="{ percentage }">
        <span class="percentage-value">{{ percentage }}%</span>
      </template>
    </el-progress>
    <div class="status-text">
      <el-tag :type="statusType">{{ statusText }}</el-tag>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'PENDING'
  },
  progress: {
    type: Number,
    default: 0
  }
})

const statusType = computed(() => {
  const statusMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'SUCCESS': 'success',
    'FAILED': 'danger'
  }
  return statusMap[props.status] || 'info'
})

const statusText = computed(() => {
  const textMap = {
    'PENDING': '等待中',
    'RUNNING': '处理中',
    'SUCCESS': '已完成',
    'FAILED': '失败'
  }
  return textMap[props.status] || '未知'
})
</script>

<style scoped>
.export-progress {
  padding: 20px;
}

.percentage-value {
  font-weight: bold;
  color: #409eff;
}

.status-text {
  margin-top: 10px;
  text-align: center;
}
</style>
