<!-- frontend/src/views/TemplateForm.vue -->
<template>
  <div class="template-form">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>{{ isEdit ? '编辑模板' : '新建模板' }}</span>
          </div>
        </template>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入模板名称" />
        </el-form-item>

        <el-form-item label="模板描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入模板描述"
          />
        </el-form-item>

        <el-form-item label="数据源" prop="data_source_id">
          <el-select 
            v-model="form.data_source_id" 
            clearable 
            filterable 
            placeholder="选择数据源（加载中...）" 
            style="width: 100%"
          >
            <el-option 
              v-for="ds in dataSources" 
              :key="ds.id" 
              :label="ds.name" 
              :value="ds.id" 
            />
          </el-select>
        </el-form-item>

        <el-form-item label="SQL 语句" prop="sql">
          <el-input
            v-model="form.sql"
            type="textarea"
            :rows="8"
            placeholder='输入 SQL 语句，使用 ${param_name} 或 :param_name 作为参数占位符&#10;示例：SELECT * FROM orders WHERE date >= ${start_date}'
          />
        </el-form-item>

        <!-- 查询参数编辑器 -->
        <el-form-item label="查询参数">
          <div class="params-editor">
            <div class="params-toolbar">
              <el-button type="primary" size="small" @click="addParam">
                <el-icon><Plus /></el-icon>添加参数
              </el-button>
              <el-button type="warning" size="small" @click="autodetectParams" style="margin-left: 8px;">
                <el-icon><Search /></el-icon>从 SQL 自动识别
              </el-button>
            </div>

            <el-table v-if="paramList.length > 0" :data="paramList" border style="margin-top: 12px;">
              <el-table-column label="参数名" width="160">
                <template #default="{ row }">
                  <el-input v-model="row.name" placeholder="如 start_date" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="标签" width="160">
                <template #default="{ row }">
                  <el-input v-model="row.label" placeholder="如 开始日期" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="类型" width="150">
                <template #default="{ row }">
                  <el-select v-model="row.type" size="small" style="width: 100%">
                    <el-option label="文本" value="string" />
                    <el-option label="数字" value="number" />
                    <el-option label="日期" value="date" />
                    <el-option label="日期范围" value="daterange" />
                    <el-option label="下拉选择" value="select" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="默认值" width="160">
                <template #default="{ row }">
                  <el-input v-model="row.default" placeholder="可选" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="下拉选项" width="200" v-if="hasSelectParam">
                <template #default="{ row }">
                  <el-input v-if="row.type === 'select'" v-model="row.optionsStr" placeholder="选项1,选项2" size="small" />
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="必填" width="70" align="center">
                <template #default="{ row }">
                  <el-switch v-model="row.required" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button type="danger" size="small" link @click="removeParam($index)">
                    <el-icon><Close /></el-icon>
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>

        <el-form-item label="是否公开" prop="is_public">
          <el-switch v-model="form.is_public" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading">
            保存
          </el-button>
          <el-button @click="handleCancel">取消</el-button>
          <el-button @click="handlePreview" :loading="previewing" v-if="isEdit">
            预览查询结果
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 查询结果预览 -->
      <el-card v-if="queryResult" style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>查询结果预览</span>
            <el-button @click="queryResult = null">关闭</el-button>
          </div>
        </template>
        <el-table :data="queryResult.rows" style="width: 100%" max-height="400">
          <el-table-column
            v-for="(column, index) in queryResult.columns"
            :key="index"
            :prop="index.toString()"
            :label="column"
            :width="150"
          />
        </el-table>
        <div class="result-footer">
          <div class="result-info">共 {{ queryResult.total }} 条记录，执行时间：{{ queryResult.execution_time_ms }}ms</div>
          <el-pagination
            background
            layout="prev, pager, next, sizes, total"
            :total="queryResult.total"
            :page-size="pageSize"
            :page-sizes="[20, 50, 100, 200]"
            :current-page="currentPage"
            @current-change="handlePageChange"
            @update:page-size="(val) => { pageSize = val; handlePageChange(1) }"
          />
        </div>
      </el-card>
    </el-card>
  </div></template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search, Close } from '@element-plus/icons-vue'
import { getTemplate, createTemplate, updateTemplate } from '@/api/template'
import { getDataSourceList } from '@/api/data_source'
import { executeQuery } from '@/api/query'
const router = useRouter()
const route = useRoute()
const formRef = ref(null)
const loading = ref(false)
const previewing = ref(false)
const queryResult = ref(null)
const currentPage = ref(1)
const pageSize = ref(50)

const isEdit = computed(() => !!route.params.id)

const form = ref({
  name: '',
  description: '',
  data_source_id: null,
  sql: '',
  params: [],
  is_public: false
})

// 参数编辑列表
const paramList = ref([])
const dataSources = ref([])

const hasSelectParam = computed(() => paramList.value.some(p => p.type === 'select'))

const rules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  sql: [{ required: true, message: '请输入 SQL 语句', trigger: 'blur' }],
  data_source_id: [{ required: true, message: '请选择数据源', trigger: 'change' }]
}

// 从 config 还原到表单
const restoreFromConfig = (config) => {
  form.data_source_id = config.data_source_id || null
  form.sql = config.sql || ''
  paramList.value = (config.params || []).map(p => ({
    name: p.name || '',
    label: p.label || p.name || '',
    type: p.type || 'string',
    default: p.default || '',
    required: p.required || false,
    optionsStr: Array.isArray(p.options) ? p.options.join(',') : ''
  }))
}

// 从表单构建 config
const buildConfig = () => {
  
  const dsId = form.value.data_source_id
  const sql = form.value.sql
  
  
  const upperSql = (form.sql || '').toUpperCase().trim()
  if (/\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE|ALTER\s+TABLE)\b/i.test(upperSql)) {
    ElMessage.error('SQL 包含危险操作（DROP/TRUNCATE/ALTER），已拒绝')
    return null
  }

  const params = paramList.value
    .filter(p => p.name.trim())
    .map(p => {
      const param = {
        name: p.name.trim(),
        label: p.label || p.name.trim(),
        type: p.type || 'string',
        required: p.required || false
      }
      if (p.default !== '' && p.default !== null) param.default = p.default
      if (p.type === 'select') param.options = (p.optionsStr || '').split(',').filter(Boolean)
      return param
    })

  return {
    data_source_id: form.value.data_source_id,
    sql: form.value.sql,
    params: params.length > 0 ? params : []
  }
}

// 自动从 SQL 识别 ${xxx} 和 :xxx 占位符
const autodetectParams = () => {
  const placeholders = new Set()
  const regex1 = /\$\{(\w+)\}/g
  let match
  const sql = form.value.sql
  while ((match = regex1.exec(sql)) !== null) {
    placeholders.add(match[1])
  }
  const regex2 = /(?<!['"\w]):(\w+)/g
  while ((match = regex2.exec(sql)) !== null) {
    placeholders.add(match[1])
  }

  if (placeholders.size === 0) {
    ElMessage.info('未检测到参数占位符（${xxx} 或 :xxx），示例：SELECT * FROM orders WHERE date >= ${start_date}')
    return
  }

  const existingNames = new Set(paramList.value.map(p => p.name))
  const newParams = [...placeholders]
    .filter(n => !existingNames.has(n))
    .map(n => ({ name: n, label: n, type: 'string', default: '', required: false, optionsStr: '' }))

  paramList.value = [...paramList.value, ...newParams]
  ElMessage.success(`已识别 ${newParams.length} 个新参数`)
}

const addParam = () => {
  paramList.value.push({ name: '', label: '', type: 'string', default: '', required: false, optionsStr: '' })
}

const removeParam = (index) => {
  paramList.value.splice(index, 1)
}

const loadTemplate = async () => {
  try {
    const response = await getTemplate(route.params.id)
    
    // 直接从后端加载配置覆盖表单
    form.value.name = response.name || ''
    form.value.description = response.description || ''
    form.value.is_public = response.is_public || false
    form.value.data_source_id = response.config?.data_source_id || null
    form.value.sql = response.config?.sql || ''
    form.value.params = response.config?.params || []
    
    // 重建参数编辑列表
    paramList.value = (response.config?.params || []).map(p => ({
      name: p.name || '',
      label: p.label || p.name || '',
      type: p.type || 'string',
      default: p.default || '',
      required: p.required || false,
      optionsStr: Array.isArray(p.options) ? p.options.join(',') : ''
    }))
    
  } catch (error) {
    console.error('[TemplateForm] 加载模板失败:', error)
    ElMessage.error('加载模板失败')
  }
}

const loadDataSources = async () => {
  try {
    const res = await getDataSourceList({ page: 1, page_size: 100 })
    // 后端直接返回数组，无需 res.items
    dataSources.value = Array.isArray(res) ? res : (res.items || [])
  } catch (error) {
    console.error('[TemplateForm] 数据源加载失败:', error)
    ElMessage.error('加载数据源失败，请刷新页面重试')
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  doPreview()
}

const handlePreview = async () => {
  currentPage.value = 1
  await doPreview()
}

const doPreview = async () => {
  const config = buildConfig()
  if (!config) return

  if (!config.data_source_id) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!config.sql) {
    ElMessage.warning('请输入 SQL 语句')
    return
  }

  // 将 params 数组转换为 dict 格式
  const paramsDict = {}
  if (config.params && config.params.length > 0) {
    config.params.forEach(p => {
      // 使用默认值（如果有）
      paramsDict[p.name] = p.default || ''
    })
  }

  // 将 SQL 中的 ${xxx} 替换为实际值（兼容后端旧代码）
  let sql = config.sql
  if (config.params && config.params.length > 0) {
    config.params.forEach(p => {
      const value = p.default || ''
      // 替换 ${param_name} 为实际值
      sql = sql.replace(new RegExp(`\\$\\{${p.name}\\}`, 'g'), value)
    })
  }

  try {
    previewing.value = true
    const response = await executeQuery({
      data_source_id: config.data_source_id,
      sql: sql,
      params: paramsDict,
      page: currentPage.value,
      page_size: pageSize.value
    })
    queryResult.value = response
    ElMessage.success('查询成功')
  } catch (error) {
    const msg = error.response?.data?.message || error.response?.data?.detail || error.message || '未知错误'
    ElMessage.error('查询失败：' + msg)
  } finally {
    previewing.value = false
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()

    const config = buildConfig()
    if (!config) {
      console.error('[TemplateForm] buildConfig 返回 null, form:', form.value)
      ElMessage.error('请检查表单：数据源和SQL不能为空')
      return
    }

    // 构建后端期望的 payload 结构
    const payload = {
      name: form.value.name,
      description: form.value.description,
      config: config,
      is_public: form.value.is_public
    }

    loading.value = true

    if (isEdit.value) {
      await updateTemplate(route.params.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createTemplate(payload)
      ElMessage.success('创建成功')
    }

    router.push('/templates')
  } catch (error) {
    console.error('[TemplateForm] 保存失败:', error)
    // 尝试获取后端返回的具体错误信息
    const detail = error.response?.data?.detail || error.message || '未知错误'
    ElMessage.error('保存失败：' + detail)
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/templates')
  }
}

onMounted(async () => {
  // 先加载数据源
  await loadDataSources()
  // 再加载模板（如果是编辑模式）
  if (isEdit.value) {
    await loadTemplate()
  }
})
</script>

<style scoped>
.template-form {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.params-editor {
  width: 100%;
}

.params-toolbar {
  margin-bottom: 8px;
}

.result-footer {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-info {
  font-size: 13px;
  color: #909399;
}
</style>
