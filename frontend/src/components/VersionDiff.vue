<!-- frontend/src/components/VersionDiff.vue -->
<template>
  <div class="version-diff">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>版本对比 - v{{ version1 }} vs v{{ version2 }}</span>
          <el-button @click="handleClose">关闭</el-button>
        </div>
      </template>

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="error" class="error-container">
        <el-alert
          :title="error"
          type="error"
          :closable="false"
          show-icon
        />
      </div>

      <div v-else-if="diffData">
        <!-- 版本信息 -->
        <el-descriptions title="版本信息" :column="2" border style="margin-bottom: 20px">
          <el-descriptions-item label="版本1">
            v{{ diffData.version1?.version || version1 }}
          </el-descriptions-item>
          <el-descriptions-item label="版本2">
            v{{ diffData.version2?.version || version2 }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间1">
            {{ formatDate(diffData.version1?.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间2">
            {{ formatDate(diffData.version2?.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="创建者1">
            {{ diffData.version1?.created_by || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建者2">
            {{ diffData.version2?.created_by || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 配置差异 -->
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane label="SQL 差异" name="sql">
            <div v-if="diffData.changes?.sql" class="diff-section">
              <div v-if="diffData.changes.sql.added?.length" class="diff-added">
                <h4>新增</h4>
                <pre><code>{{ formatCode(diffData.changes.sql.added) }}</code></pre>
              </div>
              <div v-if="diffData.changes.sql.removed?.length" class="diff-removed">
                <h4>删除</h4>
                <pre><code>{{ formatCode(diffData.changes.sql.removed) }}</code></pre>
              </div>
              <div v-if="diffData.changes.sql.modified?.length" class="diff-modified">
                <h4>修改</h4>
                <div v-for="(item, index) in diffData.changes.sql.modified" :key="index" class="diff-item">
                  <div class="diff-old">
                    <strong>旧值:</strong>
                    <pre><code>{{ formatCode(item.old) }}</code></pre>
                  </div>
                  <div class="diff-new">
                    <strong>新值:</strong>
                    <pre><code>{{ formatCode(item.new) }}</code></pre>
                  </div>
                </div>
              </div>
              <el-empty v-if="!hasSqlChanges" description="无 SQL 差异" />
            </div>
            <el-empty v-else description="无 SQL 差异数据" />
          </el-tab-pane>

          <el-tab-pane label="布局差异" name="layout">
            <div v-if="diffData.changes?.layout" class="diff-section">
              <div v-if="diffData.changes.layout.added?.length" class="diff-added">
                <h4>新增</h4>
                <pre><code>{{ formatCode(diffData.changes.layout.added) }}</code></pre>
              </div>
              <div v-if="diffData.changes.layout.removed?.length" class="diff-removed">
                <h4>删除</h4>
                <pre><code>{{ formatCode(diffData.changes.layout.removed) }}</code></pre>
              </div>
              <div v-if="diffData.changes.layout.modified?.length" class="diff-modified">
                <h4>修改</h4>
                <div v-for="(item, index) in diffData.changes.layout.modified" :key="index" class="diff-item">
                  <div class="diff-old">
                    <strong>旧值:</strong>
                    <pre><code>{{ formatCode(item.old) }}</code></pre>
                  </div>
                  <div class="diff-new">
                    <strong>新值:</strong>
                    <pre><code>{{ formatCode(item.new) }}</code></pre>
                  </div>
                </div>
              </div>
              <el-empty v-if="!hasLayoutChanges" description="无布局差异" />
            </div>
            <el-empty v-else description="无布局差异数据" />
          </el-tab-pane>

          <el-tab-pane label="样式差异" name="style">
            <div v-if="diffData.changes?.style" class="diff-section">
              <div v-if="diffData.changes.style.added?.length" class="diff-added">
                <h4>新增</h4>
                <pre><code>{{ formatCode(diffData.changes.style.added) }}</code></pre>
              </div>
              <div v-if="diffData.changes.style.removed?.length" class="diff-removed">
                <h4>删除</h4>
                <pre><code>{{ formatCode(diffData.changes.style.removed) }}</code></pre>
              </div>
              <div v-if="diffData.changes.style.modified?.length" class="diff-modified">
                <h4>修改</h4>
                <div v-for="(item, index) in diffData.changes.style.modified" :key="index" class="diff-item">
                  <div class="diff-old">
                    <strong>旧值:</strong>
                    <pre><code>{{ formatCode(item.old) }}</code></pre>
                  </div>
                  <div class="diff-new">
                    <strong>新值:</strong>
                    <pre><code>{{ formatCode(item.new) }}</code></pre>
                  </div>
                </div>
              </div>
              <el-empty v-if="!hasStyleChanges" description="无样式差异" />
            </div>
            <el-empty v-else description="无样式差异数据" />
          </el-tab-pane>

          <el-tab-pane label="JSON 对比" name="json">
            <div class="json-compare">
              <div class="json-panel">
                <h4>版本 {{ version1 }} JSON</h4>
                <pre><code>{{ formatJson(diffData.version1?.config) }}</code></pre>
              </div>
              <div class="json-panel">
                <h4>版本 {{ version2 }} JSON</h4>
                <pre><code>{{ formatJson(diffData.version2?.config) }}</code></pre>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="完整差异" name="full">
            <div v-if="diffData.changes" class="diff-section">
              <div v-if="diffData.changes.added?.length" class="diff-added">
                <h4>新增项</h4>
                <el-tag
                  v-for="(item, index) in diffData.changes.added"
                  :key="index"
                  style="margin: 5px"
                >
                  {{ item }}
                </el-tag>
              </div>
              <div v-if="diffData.changes.removed?.length" class="diff-removed">
                <h4>删除项</h4>
                <el-tag
                  v-for="(item, index) in diffData.changes.removed"
                  :key="index"
                  type="danger"
                  style="margin: 5px"
                >
                  {{ item }}
                </el-tag>
              </div>
              <div v-if="diffData.changes.modified?.length" class="diff-modified">
                <h4>修改项</h4>
                <div v-for="(item, index) in diffData.changes.modified" :key="index" class="diff-item">
                  <el-tag>{{ item.key }}</el-tag>
                  <div class="diff-values">
                    <span class="diff-old-text">旧值: {{ formatValue(item.old) }}</span>
                    <span class="diff-new-text">新值: {{ formatValue(item.new) }}</span>
                  </div>
                </div>
              </div>
              <el-empty v-if="!hasFullChanges" description="无差异" />
            </div>
            <el-empty v-else description="无差异数据" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getVersionDiff } from '@/api/template'

const props = defineProps({
  templateId: {
    type: [Number, String],
    required: true
  },
  version1: {
    type: [Number, String],
    required: true
  },
  version2: {
    type: [Number, String],
    required: true
  }
})

const emit = defineEmits(['close'])

const loading = ref(false)
const error = ref('')
const diffData = ref(null)
const activeTab = ref('sql')

// 计算属性：检查是否有 SQL 变化
const hasSqlChanges = computed(() => {
  const sql = diffData.value?.changes?.sql
  return sql && (
    (sql.added && sql.added.length > 0) ||
    (sql.removed && sql.removed.length > 0) ||
    (sql.modified && sql.modified.length > 0)
  )
})

// 计算属性：检查是否有布局变化
const hasLayoutChanges = computed(() => {
  const layout = diffData.value?.changes?.layout
  return layout && (
    (layout.added && layout.added.length > 0) ||
    (layout.removed && layout.removed.length > 0) ||
    (layout.modified && layout.modified.length > 0)
  )
})

// 计算属性：检查是否有样式变化
const hasStyleChanges = computed(() => {
  const style = diffData.value?.changes?.style
  return style && (
    (style.added && style.added.length > 0) ||
    (style.removed && style.removed.length > 0) ||
    (style.modified && style.modified.length > 0)
  )
})

// 计算属性：检查是否有完整变化
const hasFullChanges = computed(() => {
  const changes = diffData.value?.changes
  return changes && (
    (changes.added && changes.added.length > 0) ||
    (changes.removed && changes.removed.length > 0) ||
    (changes.modified && changes.modified.length > 0)
  )
})

onMounted(async () => {
  await loadDiff()
})

const loadDiff = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const response = await getVersionDiff(
      props.templateId,
      props.version1,
      props.version2
    )
    diffData.value = response
    ElMessage.success('版本差异加载成功')
  } catch (err) {
    console.error('获取版本差异失败:', err)
    error.value = '获取版本差异失败，请稍后重试'
    ElMessage.error('获取版本差异失败')
  } finally {
    loading.value = false
  }
}

const handleClose = () => {
  emit('close')
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const formatCode = (data) => {
  if (typeof data === 'string') {
    return data
  }
  if (Array.isArray(data)) {
    return data.join('\n')
  }
  return JSON.stringify(data, null, 2)
}

const formatJson = (data) => {
  if (!data) return '{}'
  return JSON.stringify(data, null, 2)
}

const formatValue = (value) => {
  if (value === null || value === undefined) {
    return 'null'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}
</script>

<style scoped>
.version-diff {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loading-container {
  padding: 20px;
}

.error-container {
  padding: 20px;
}

.diff-section {
  padding: 10px;
}

.diff-added {
  margin-bottom: 20px;
}

.diff-added h4 {
  color: #67c23a;
  margin-bottom: 10px;
}

.diff-removed {
  margin-bottom: 20px;
}

.diff-removed h4 {
  color: #f56c6c;
  margin-bottom: 10px;
}

.diff-modified {
  margin-bottom: 20px;
}

.diff-modified h4 {
  color: #e6a23c;
  margin-bottom: 10px;
}

.diff-item {
  margin: 15px 0;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.diff-old {
  margin-bottom: 10px;
}

.diff-old strong {
  color: #f56c6c;
}

.diff-new strong {
  color: #67c23a;
}

.diff-values {
  margin-top: 5px;
}

.diff-old-text {
  color: #f56c6c;
  margin-right: 15px;
}

.diff-new-text {
  color: #67c23a;
}

.json-compare {
  display: flex;
  gap: 20px;
}

.json-panel {
  flex: 1;
}

.json-panel h4 {
  margin-bottom: 10px;
  color: #409eff;
}

pre {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 0;
}

code {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
}
</style>
