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

        <el-form-item label="模板配置" prop="config">
          <el-input
            v-model="configJson"
            type="textarea"
            :rows="10"
            placeholder='请输入模板配置（JSON 格式），例如：\n{\n  "data_source_id": 1,\n  "sql": "SELECT * FROM users",\n  "params": {}\n}'
          />
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
import { getTemplate, createTemplate, updateTemplate } from '@/api/template'
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
  config: {},
  is_public: false
})

const configJson = ref('')

const rules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  config: [{ required: true, message: '请输入模板配置', trigger: 'blur' }]
}

onMounted(async () => {
  if (isEdit.value) {
    await loadTemplate()
  }
})

const loadTemplate = async () => {
  try {
    const response = await getTemplate(route.params.id)
    form.value = {
      name: response.name,
      description: response.description,
      config: response.config,
      is_public: response.is_public
    }
    configJson.value = JSON.stringify(response.config, null, 2)
  } catch (error) {
    ElMessage.error('加载模板失败')
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
  try {
    previewing.value = true
    const config = JSON.parse(configJson.value)

    if (!config.data_source_id && !config.sql) {
      ElMessage.warning('模板配置中缺少 data_source_id（数据源ID）和 sql（SQL语句）')
      return
    }
    if (!config.data_source_id) {
      ElMessage.warning('模板配置中缺少 data_source_id（数据源ID）')
      return
    }
    if (!config.sql) {
      ElMessage.warning('模板配置中缺少 sql（SQL语句）')
      return
    }

    const response = await executeQuery({
      data_source_id: config.data_source_id,
      sql: config.sql,
      params: config.params || {},
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
    // 验证表单
    await formRef.value.validate()

    // 解析 JSON 配置
    try {
      form.value.config = JSON.parse(configJson.value)
    } catch (error) {
      ElMessage.error('模板配置格式错误，请输入有效的 JSON')
      return
    }

    loading.value = true

    if (isEdit.value) {
      await updateTemplate(route.params.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createTemplate(form.value)
      ElMessage.success('创建成功')
    }

    router.push('/templates')
  } catch (error) {
    ElMessage.error('保存失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  // 尝试返回上一页，如果没有历史记录则返回模板列表
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/templates')
  }
}
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
</style>
