<template>
  <div class="layout-list-page">
    <div class="page-header">
      <h2>仪表盘布局</h2>
      <el-button type="primary" @click="handleCreate">新建布局</el-button>
    </div>

    <StaticTableEnhancer :columns="tableColumns" :data="layouts" :loading="loading" table-id="layout-list">
      <template #is_default="{ row }">
        <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
        <el-button v-else size="small" text @click="setDefault(row)">设为默认</el-button>
      </template>
      <template #widget_count="{ row }">
        {{ row.widget_count || 0 }}
      </template>
      <template #updated_at="{ row }">
        {{ row.updated_at ? new Date(row.updated_at).toLocaleString() : '-' }}
      </template>
      <template #operations="{ row }">
        <el-button size="small" @click="viewLayout(row.id)">查看</el-button>
        <el-button size="small" text @click="renameLayout(row)">重命名</el-button>
        <el-button size="small" text type="danger" :disabled="row.is_default" @click="handleDelete(row)">删除</el-button>
      </template>
    </StaticTableEnhancer>

    <el-dialog v-model="showRenameDialog" title="重命名布局" width="400px">
      <el-input v-model="renameValue" placeholder="布局名称" />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { getLayoutList, updateLayout, deleteLayout, createLayout } from "@/api/dashboard"
import StaticTableEnhancer from '@/components/StaticTableEnhancer.vue'

const router = useRouter()
const loading = ref(true)
const layouts = ref([])
const showRenameDialog = ref(false)
const renameValue = ref("")
let renameTarget = null

const tableColumns = [
  { prop: 'name', label: '名称', minWidth: 200 },
  { prop: 'is_default', label: '默认', width: 100, align: 'center', slotName: 'is_default' },
  { prop: 'widget_count', label: '组件数', width: 100, align: 'center', slotName: 'widget_count' },
  { prop: 'updated_at', label: '更新时间', width: 180, slotName: 'updated_at' },
  { prop: 'operations', label: '操作', width: 200, slotName: 'operations' },
]

const loadLayouts = async () => {
  loading.value = true
  try {
    layouts.value = await getLayoutList()
  } catch {
    ElMessage.error("加载布局列表失败")
  } finally {
    loading.value = false
  }
}

const viewLayout = (id) => {
  router.push({ name: "Dashboard" })
}

const handleCreate = async () => {
  try {
    const layout = await createLayout({ name: "新建布局" })
    ElMessage.success("布局已创建")
    await loadLayouts()
    router.push({ name: "Dashboard" })
  } catch {
    ElMessage.error("创建失败")
  }
}

const setDefault = async (row) => {
  try {
    await updateLayout(row.id, { is_default: true })
    ElMessage.success("已设为默认布局")
    await loadLayouts()
  } catch {
    ElMessage.error("操作失败")
  }
}

const renameLayout = (row) => {
  renameTarget = row
  renameValue.value = row.name
  showRenameDialog.value = true
}

const confirmRename = async () => {
  if (!renameValue.value.trim() || !renameTarget) return
  try {
    await updateLayout(renameTarget.id, { name: renameValue.value.trim() })
    ElMessage.success("已重命名")
    await loadLayouts()
  } catch {
    ElMessage.error("重命名失败")
  }
  showRenameDialog.value = false
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除布局「${row.name}」？`, "确认删除", {
      confirmButtonText: "确定删除", cancelButtonText: "取消", type: "warning",
    })
    await deleteLayout(row.id)
    ElMessage.success("已删除")
    await loadLayouts()
  } catch { /* cancelled */ }
}

onMounted(loadLayouts)
</script>

<style scoped>
.layout-list-page {
  padding: 20px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
</style>
