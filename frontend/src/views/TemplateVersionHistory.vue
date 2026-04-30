<!-- frontend/src/views/TemplateVersionHistory.vue -->
<template>
  <div class="template-version-history">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>模板版本历史</span>
            <el-button @click="handleBack">返回</el-button>
          </div>
        </template>

        <el-table :data="versions" style="width: 100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="version" label="版本号" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_by" label="创建者" width="100" />
          <el-table-column label="操作" width="250">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="handleView(row)">
                查看
              </el-button>
              <el-button type="success" size="small" @click="handleRollback(row)">
                回滚
              </el-button>
              <el-button type="info" size="small" @click="handleCompare(row)">
                对比
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="selectedVersion" style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>版本详情 - {{ selectedVersion.version }}</span>
          </div>
        </template>

        <pre>{{ JSON.stringify(selectedVersion.config, null, 2) }}</pre>
      </el-card>

      <!-- 对比对话框 -->
      <el-dialog v-model="compareDialogVisible" title="选择对比版本" width="400px">
        <el-form label-width="100px">
          <el-form-item label="对比版本">
            <el-select v-model="compareVersion" placeholder="请选择版本">
              <el-option
                v-for="v in versions"
                :key="v.version"
                :label="`v${v.version}`"
                :value="v.version"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="compareDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleConfirmCompare">确定</el-button>
        </template>
      </el-dialog>

      <!-- 版本对比组件 -->
      <VersionDiff
        v-if="versionDiffVisible"
        :template-id="templateId"
        :version1="version1"
        :version2="version2"
        @close="handleCloseVersionDiff"
      />
    </div></template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateVersions, rollbackTemplate, getVersionDiff } from '@/api/template'
import VersionDiff from '@/components/VersionDiff.vue'

const route = useRoute()
const router = useRouter()
const templateId = ref(parseInt(route.params.id))
const versions = ref([])
const selectedVersion = ref(null)
const compareDialogVisible = ref(false)
const compareVersion = ref(null)
const baseVersion = ref(null)
const versionDiffVisible = ref(false)
const version1 = ref(null)
const version2 = ref(null)

onMounted(async () => {
  await loadVersions()
})

const loadVersions = async () => {
  try {
    const response = await getTemplateVersions(templateId.value)
    versions.value = response
  } catch (error) {
    ElMessage.error('加载版本列表失败')
  }
}

const handleBack = () => {
  router.push(`/templates/${templateId.value}`)
}

const handleView = (row) => {
  selectedVersion.value = row
}

const handleRollback = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 v${row.version} 吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await rollbackTemplate(templateId.value, row.version)
    ElMessage.success('回滚成功')
    await loadVersions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('回滚失败')
    }
  }
}

const handleCompare = (row) => {
  baseVersion.value = row.version
  compareVersion.value = null
  compareDialogVisible.value = true
}

const handleConfirmCompare = async () => {
  if (!compareVersion.value) {
    ElMessage.warning('请选择对比版本')
    return
  }

  try {
    version1.value = baseVersion.value
    version2.value = compareVersion.value
    versionDiffVisible.value = true
    compareDialogVisible.value = false
  } catch (error) {
    ElMessage.error('打开版本对比失败')
  }
}

const handleCloseVersionDiff = () => {
  versionDiffVisible.value = false
}

const formatDate = (date) => {
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<style scoped>
.template-version-history {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

pre {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>
