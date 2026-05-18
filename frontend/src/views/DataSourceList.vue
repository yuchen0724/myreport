<template>
  <div class="datasource-list">
    <div class="toolbar">
      <el-button type="primary" @click="handleCreate">新建数据源</el-button>
    </div>
    <StaticTableEnhancer
      :columns="tableColumns"
      :data="dataSources"
      :loading="loading"
      table-id="datasource-list"
    >
      <template #load_group="{ row }">
        <el-tag :type="row.load_group ? 'success' : 'info'" size="small">
          {{ row.load_group ? '是' : '否' }}
        </el-tag>
      </template>
      <template #is_active="{ row }">
        <el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
      </template>
      <template #operations="{ row }">
        <el-button size="small" @click="handleEdit(row)">编辑</el-button>
        <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
      </template>
    </StaticTableEnhancer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDataSourceList, deleteDataSource } from '@/api/data_source'
import StaticTableEnhancer from '@/components/StaticTableEnhancer.vue'

const router = useRouter()
const loading = ref(false)
const dataSources = ref([])

const tableColumns = [
  { prop: 'name', label: '名称' },
  { prop: 'type', label: '类型' },
  { prop: 'host', label: '主机' },
  { prop: 'port', label: '端口' },
  { prop: 'database', label: '数据库' },
  { prop: 'load_group', label: '加载集团', width: 90, slotName: 'load_group' },
  { prop: 'is_active', label: '状态', slotName: 'is_active' },
  { prop: 'operations', label: '操作', width: 200, slotName: 'operations' },
]

const loadDataSources = async () => {
  loading.value = true
  try {
    dataSources.value = await getDataSourceList()
  } catch (error) {
    ElMessage.error('加载数据源失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => router.push('/datasources/create')
const handleEdit = (row) => router.push(`/datasources/${row.id}/edit`)

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该数据源吗？', '提示', { type: 'warning' })
    await deleteDataSource(row.id)
    ElMessage.success('删除成功')
    loadDataSources()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => loadDataSources())
</script>

<style scoped>
.datasource-list {
  padding: 20px;
}
.toolbar {
  margin-bottom: 20px;
}
</style>
