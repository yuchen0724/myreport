<!-- frontend/src/views/TemplateForm.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
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
            placeholder="请输入模板配置（JSON 格式）"
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
        </el-form-item>
      </el-form>
    </el-card>
  </div>
  </Layout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTemplate, createTemplate, updateTemplate } from '@/api/template'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

const router = useRouter()
const route = useRoute()
const formRef = ref(null)
const loading = ref(false)

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
  router.push('/templates')
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
