<!-- frontend/src/views/TemplateDetail.vue -->
<template>
  <div class="template-detail">
      <el-card v-if="template">
        <template #header>
          <div class="card-header">
            <span>模板详情</span>
            <div>
              <el-button @click="handleEdit" v-if="!isReadOnly">编辑</el-button>
              <el-button @click="handleBack">返回</el-button>
            </div>
          </div>
        </template>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="模板ID">{{ template.id }}</el-descriptions-item>
          <el-descriptions-item label="模板名称">{{ template.name }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ template.version }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="template.is_public ? 'success' : 'info'">
              {{ template.is_public ? '公开' : '私有' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(template.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(template.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ template.description || '无' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <div class="config-section">
          <h3>模板配置</h3>
          <pre class="config-json">{{ formatConfig(template.config) }}</pre>
        </div>

        <el-divider />

        <div class="actions-section">
          <el-button type="primary" @click="handlePreview" :loading="previewing">
            预览查询结果
          </el-button>
          <el-button @click="handleVersions">查看版本历史</el-button>
          <el-button @click="handleShare" v-if="!isReadOnly">分享模板</el-button>
          <el-button 
            :type="isFavorited ? 'warning' : 'info'" 
            @click="toggleFavorite"
          >
            {{ isFavorited ? '取消收藏' : '添加收藏' }}
          </el-button>
        </div>

        <!-- 查询结果预览 -->
        <el-card v-if="queryResult" style="margin-top: 20px;">
          <template #header>
            <div class="card-header">
              <span>查询结果预览</span>
              <el-button @click="queryResult = null">关闭</el-button>
            </div>
          </template>
          <EnhancedTable
            v-if="detailTableData.length > 0"
            :data="detailTableData"
            :columns="queryResult.columns"
            :loading="previewing"
            table-id="template-preview"
            :summarizable="false"
            :enable-expand="false"
            :searchable="true"
            :max-height="400"
          />
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

      <el-card v-else>
        <el-empty description="加载中..." />
      </el-card>
    </div></template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTemplate } from '@/api/template'
import { executeQuery } from '@/api/query'
import { checkFavorite, addFavorite, removeFavoriteByTemplate } from '@/api/favorite'
import EnhancedTable from '@/components/EnhancedTable.vue'

// 将索引数组 rows 转换为对象数组
const detailTableData = computed(() => {
  if (!queryResult.value?.rows || !queryResult.value?.columns) return []
  const cols = queryResult.value.columns
  return queryResult.value.rows.map(row => {
    const obj = {}
    cols.forEach((col, i) => { obj[col] = row[i] })
    return obj
  })
})
const router = useRouter()
const route = useRoute()
const template = ref(null)
const previewing = ref(false)
const queryResult = ref(null)
const currentPage = ref(1)
const pageSize = ref(50)
const isFavorited = ref(false)
const favoriteId = ref(null)

const isReadOnly = computed(() => route.query.readOnly === 'true')

onMounted(async () => {
  await loadTemplate()
  await checkIsFavorited()
})

const loadTemplate = async () => {
  try {
    const response = await getTemplate(route.params.id)
    template.value = response
  } catch (error) {
    ElMessage.error('加载模板失败：' + (error.message || '未知错误'))
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}

const formatConfig = (config) => {
  return JSON.stringify(config, null, 2)
}

const handleEdit = () => {
  router.push(`/templates/${template.value.id}/edit`).catch(err => {
    ElMessage.error('无法编辑模板')
  })
}

const handleBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/templates')
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
    const config = template.value.config

    if (!config.data_source_id && !config.sql) {
      ElMessage.warning('模板配置中缺少 data_source_id（数据源ID）和 sql（SQL语句），请在编辑模板时补充')
      return
    }
    if (!config.data_source_id) {
      ElMessage.warning('模板配置中缺少 data_source_id（数据源ID），请在编辑模板时补充')
      return
    }
    if (!config.sql) {
      ElMessage.warning('模板配置中缺少 sql（SQL语句），请在编辑模板时补充')
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

const handleVersions = () => {
  router.push(`/templates/${template.value.id}/versions`)
}

const handleShare = () => {
  router.push(`/template-share?templateId=${template.value.id}`)
}

const checkIsFavorited = async () => {
  try {
    const res = await checkFavorite(route.params.id)
    isFavorited.value = res.is_favorited
  } catch (error) {
    console.error('检查收藏状态失败', error)
  }
}

const toggleFavorite = async () => {
  try {
    if (isFavorited.value) {
      await removeFavoriteByTemplate(parseInt(route.params.id))
      isFavorited.value = false
      ElMessage.success('已取消收藏')
    } else {
      await addFavorite({
        template_id: parseInt(route.params.id),
        category: '默认'
      })
      isFavorited.value = true
      ElMessage.success('收藏成功')
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}
</script>

<style scoped>
.template-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-section {
  margin: 20px 0;
}

.config-section h3 {
  margin-bottom: 10px;
  color: #333;
}

.config-json {
  background-color: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
}

.actions-section {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.result-footer {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.result-info {
  color: #666;
}
</style>
