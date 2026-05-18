<!-- frontend/src/views/AsyncExport.vue -->
<template>
  <div class="async-export">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>异步导出</span>
          </div>
        </template>

        <el-form :model="form" label-width="120px">
          <el-form-item label="数据源">
            <el-select v-model="form.data_source_id" placeholder="请选择数据源">
              <el-option
                v-for="ds in dataSources"
                :key="ds.id"
                :label="ds.name"
                :value="ds.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="SQL查询">
            <el-input
              v-model="form.sql"
              type="textarea"
              :rows="5"
              placeholder="请输入SQL查询语句"
            />
          </el-form-item>

          <el-form-item label="导出类型">
            <el-radio-group v-model="form.export_type">
              <el-radio value="excel">Excel</el-radio>
              <el-radio value="pdf">PDF</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="handleCreateExport" :loading="creating">
              创建导出任务
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>导出任务列表</span>
            <el-button @click="loadTasks">刷新</el-button>
          </div>
        </template>

        <StaticTableEnhancer :columns="taskColumns" :data="tasks" table-id="async-export-list">
          <template #status="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
          <template #sql="{ row }">
            {{ row.sql || '-' }}
          </template>
          <template #progress="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="10" />
          </template>
          <template #created_at="{ row }">
            {{ row.created_at ? formatDate(row.created_at) : '-' }}
          </template>
          <template #operations="{ row }">
            <el-button
              v-if="row.status === 'SUCCESS'"
              type="primary"
              size="small"
              @click="handleDownload(row.id)"
            >
              下载
            </el-button>
            <el-button
              v-if="row.status === 'FAILED'"
              type="danger"
              size="small"
              @click="handleViewError(row)"
            >
              查看错误
            </el-button>
          </template>
        </StaticTableEnhancer>
      </el-card>
    </div></template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createExportTask, getTaskStatus, getUserTasks, downloadExportFile } from '@/api/async_export'
import { getDataSourceList } from '@/api/data_source'
import StaticTableEnhancer from '@/components/StaticTableEnhancer.vue'

const form = ref({
  data_source_id: null,
  sql: '',
  export_type: 'excel'
})

const dataSources = ref([])
const tasks = ref([])
const creating = ref(false)
let refreshInterval = null

const taskColumns = [
  { prop: 'id', label: '任务ID', width: 200 },
  { prop: 'status', label: '状态', width: 100, slotName: 'status' },
  { prop: 'sql', label: 'SQL', width: 300, slotName: 'sql' },
  { prop: 'progress', label: '进度', width: 150, slotName: 'progress' },
  { prop: 'row_count', label: '行数', width: 100 },
  { prop: 'created_at', label: '创建时间', width: 180, slotName: 'created_at' },
  { prop: 'operations', label: '操作', width: 150, slotName: 'operations' },
]

const loadDataSources = async () => {
  try {
    const response = await getDataSourceList()
    dataSources.value = response
  } catch (error) {
    ElMessage.error('加载数据源失败')
  }
}

const loadTasks = async () => {
  try {
    const response = await getUserTasks()
    tasks.value = response
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  }
}

const handleCreateExport = async () => {
  if (!form.value.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.sql) {
    ElMessage.warning('请输入SQL查询')
    return
  }

  creating.value = true
  try {
    const response = await createExportTask(form.value)
    ElMessage.success('导出任务已创建')
    loadTasks()
  } catch (error) {
    ElMessage.error('创建导出任务失败')
  } finally {
    creating.value = false
  }
}

const handleDownload = async (taskId) => {
  try {
    const response = await downloadExportFile(taskId)
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `export_${taskId}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载文件失败')
  }
}

const handleViewError = (task) => {
  ElMessage.error(task.error_message || '导出失败')
}

const getStatusType = (status) => {
  const typeMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'SUCCESS': 'success',
    'FAILED': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'PENDING': '等待中',
    'RUNNING': '处理中',
    'SUCCESS': '已完成',
    'FAILED': '失败'
  }
  return textMap[status] || '未知'
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadDataSources()
  loadTasks()
  // 每5秒刷新一次任务状态
  refreshInterval = setInterval(loadTasks, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.async-export {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
