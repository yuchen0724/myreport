<!-- frontend/src/views/Favorites.vue -->
<template>
  <div class="favorites-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>我的收藏夹</span>
          <div class="filter-section">
            <el-select v-model="selectedCategory" placeholder="选择分类" clearable @change="loadFavorites">
              <el-option label="全部" value="" />
              <el-option label="默认" value="默认" />
              <el-option label="工作" value="工作" />
              <el-option label="个人" value="个人" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="favorites" v-loading="loading" style="width: 100%">
        <el-table-column prop="template_name" label="模板名称" min-width="180" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="scope">
            <el-tag :type="getCategoryType(scope.row.category)">{{ scope.row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_at" label="收藏时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button type="primary" link @click="viewTemplate(scope.row.template_id)">查看</el-button>
            <el-button type="warning" link @click="editFavorite(scope.row)">编辑</el-button>
            <el-button type="danger" link @click="handleRemove(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editDialogVisible" title="编辑收藏" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="分类">
          <el-select v-model="editForm.category" placeholder="选择分类">
            <el-option label="默认" value="默认" />
            <el-option label="工作" value="工作" />
            <el-option label="个人" value="个人" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.note" type="textarea" rows="3" placeholder="添加备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveEdit">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFavorites, updateFavorite, removeFavorite } from '@/api/favorite'

const router = useRouter()
const favorites = ref([])
const loading = ref(false)
const selectedCategory = ref('')
const editDialogVisible = ref(false)
const editForm = ref({
  id: null,
  category: '默认',
  note: ''
})

onMounted(() => {
  loadFavorites()
})

const loadFavorites = async () => {
  loading.value = true
  try {
    const res = await getFavorites(selectedCategory.value)
    favorites.value = res
  } catch (error) {
    ElMessage.error('加载收藏夹失败')
  } finally {
    loading.value = false
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

const getCategoryType = (category) => {
  const types = {
    '默认': 'info',
    '工作': 'success',
    '个人': 'warning'
  }
  return types[category] || 'info'
}

const viewTemplate = (templateId) => {
  router.push(`/templates/${templateId}`)
}

const editFavorite = (row) => {
  editForm.value = { ...row }
  editDialogVisible.value = true
}

const saveEdit = async () => {
  try {
    await updateFavorite(editForm.value.id, {
      category: editForm.value.category,
      note: editForm.value.note
    })
    ElMessage.success('更新成功')
    editDialogVisible.value = false
    loadFavorites()
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const handleRemove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要取消收藏吗？', '提示', {
      type: 'warning'
    })
    await removeFavorite(row.id)
    ElMessage.success('已取消收藏')
    loadFavorites()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}
</script>

<style scoped>
.favorites-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-section {
  display: flex;
  gap: 10px;
}
</style>
