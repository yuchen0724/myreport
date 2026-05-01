<template>
  <div class="menu-list">
    <el-card>
      <div class="card-header">
        <span>菜单管理</span>
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          新增菜单
        </el-button>
      </div>

      <el-table
        :data="menuTree"
        row-key="id"
        border
        default-expand-all
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
      >
        <el-table-column prop="name" label="菜单名称" width="200" />
        <el-table-column prop="path" label="路由路径" width="180" />
        <el-table-column prop="icon" label="图标" width="100">
          <template #default="{ row }">
            <el-icon v-if="row.icon"><component :is="row.icon" /></el-icon>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="template_name" label="关联模板" width="150">
          <template #default="{ row }">
            <span v-if="row.template_name">{{ row.template_name }}</span>
            <el-tag v-else type="info" size="small">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column prop="is_enabled" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'danger'" size="small">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_visible" label="可见" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_visible ? '' : 'warning'" size="small">
              {{ row.is_visible ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="primary" link @click="handleAddChild(row)">添加子菜单</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="上级菜单" prop="parent_id">
          <el-tree-select
            v-model="form.parent_id"
            :data="parentMenuOptions"
            :props="{ value: 'id', label: 'name', children: 'children' }"
            check-strictly
            clearable
            placeholder="选择上级菜单（不选则为顶级菜单）"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="菜单名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入菜单名称" />
        </el-form-item>
        <el-form-item label="路由路径" prop="path">
          <el-input v-model="form.path" placeholder="例如：/report/sales" />
        </el-form-item>
        <el-form-item label="图标" prop="icon">
          <el-input v-model="form.icon" placeholder="例如：Document" />
        </el-form-item>
        <el-form-item label="关联模板" prop="template_id">
          <el-select
            v-model="form.template_id"
            clearable
            filterable
            placeholder="选择报表模板（可选）"
            style="width: 100%"
          >
            <el-option
              v-for="tpl in templates"
              :key="tpl.id"
              :label="tpl.name"
              :value="tpl.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="是否启用" prop="is_enabled">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
        <el-form-item label="是否可见" prop="is_visible">
          <el-switch v-model="form.is_visible" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="2"
            placeholder="菜单备注（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getMenus, getMenuTree, createMenu, updateMenu, deleteMenu } from '@/api/menu'
import { getTemplateList } from '@/api/template'

// 数据
const menuTree = ref([])
const templates = ref([])
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const editingId = ref(null)

// 表单
const form = reactive({
  parent_id: null,
  name: '',
  path: '',
  icon: '',
  template_id: null,
  sort_order: 0,
  is_enabled: true,
  is_visible: true,
  remark: ''
})

// 验证规则
const rules = {
  name: [
    { required: true, message: '请输入菜单名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  path: [
    { required: true, message: '请输入路由路径', trigger: 'blur' }
  ],
  sort_order: [
    { required: true, message: '请输入排序值', trigger: 'blur' }
  ]
}

// 计算属性
const dialogTitle = computed(() => editingId.value ? '编辑菜单' : '新增菜单')
const parentMenuOptions = computed(() => {
  const options = [{ id: 0, name: '顶级菜单', children: [] }]
  // 过滤掉当前编辑的菜单及其子菜单防止循环引用
  const filterMenu = (menus, excludeId) => {
    return menus.filter(m => m.id !== excludeId).map(m => ({
      id: m.id,
      name: m.name,
      children: m.children ? filterMenu(m.children, excludeId) : []
    }))
  }
  options[0].children = filterMenu(menuTree.value, editingId.value)
  return options
})

// 加载数据
const loadMenus = async () => {
  try {
    const res = await getMenuTree()
    // 响应拦截器已提取 data，res 直接是数组
    menuTree.value = Array.isArray(res) ? res : (res.data || [])
  } catch (error) {
    ElMessage.error('加载菜单失败：' + (error.message || '未知错误'))
  }
}

const loadTemplate = async () => {
  try {
    const res = await getTemplateList({ page: 1, page_size: 1000 })
    // 后端直接返回数组，不需要取 items
    templates.value = Array.isArray(res) ? res : (res.data || [])
  } catch (error) {
    console.error('加载模板失败：', error)
  }
}

// 重置表单
const resetForm = () => {
  Object.assign(form, {
    parent_id: null,
    name: '',
    path: '',
    icon: '',
    template_id: null,
    sort_order: 0,
    is_enabled: true,
    is_visible: true,
    remark: ''
  })
  editingId.value = null
}

// 新增
const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

// 添加子菜单
const handleAddChild = (row) => {
  resetForm()
  form.parent_id = row.id
  dialogVisible.value = true
}

// 编辑
const handleEdit = (row) => {
  editingId.value = row.id
  Object.assign(form, {
    parent_id: row.parent_id || null,
    name: row.name,
    path: row.path,
    icon: row.icon || '',
    template_id: row.template_id || null,
    sort_order: row.sort_order || 0,
    is_enabled: row.is_enabled,
    is_visible: row.is_visible,
    remark: row.remark || ''
  })
  dialogVisible.value = true
}

// 删除
const handleDelete = async (row) => {
  if (row.children && row.children.length > 0) {
    ElMessage.warning('请先删除子菜单')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定删除菜单「${row.name}」吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await deleteMenu(row.id)
    ElMessage.success('删除成功')
    loadMenus()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败：' + (error.message || '未知错误'))
    }
  }
}

// 提交
const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    submitting.value = true
    
    const data = { ...form }
    if (!data.parent_id) data.parent_id = null
    if (!data.template_id) data.template_id = null
    
    if (editingId.value) {
      await updateMenu(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createMenu(data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadMenus()
  } catch (error) {
    if (error !== false) {
      ElMessage.error('操作失败：' + (error.message || '未知错误'))
    }
  } finally {
    submitting.value = false
  }
}

// 初始化
onMounted(() => {
  loadMenus()
  loadTemplate()
})
</script>

<style scoped>
.menu-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>