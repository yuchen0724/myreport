<!-- frontend/src/views/TemplateVersionHistory.vue -->
<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
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

      <el-card v-if="diffResult" style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>版本差异 - v{{ diffResult.version1.version }} vs v{{ diffResult.version2.version }}</span>
          </div>
        </template>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="新增" name="added">
            <el-tag
              v-for="item in diffResult.changes.added"
              :key="item"
              style="margin: 5px"
            >
              {{ item }}
            </el-tag>
            <el-empty v-if="!diffResult.changes.added.length" description="无新增项" />
          </el-tab-pane>
          <el-tab-pane label="删除" name="removed">
            <el-tag
              v-for="item in diffResult.changes.removed"
              :key="item"
              type="danger"
              style="margin: 5px"
            >
              {{ item }}
            </el-tag>
            <el-empty v-if="!diffResult.changes.removed.length" description="无删除项" />
          </el-tab-pane>
          <el-tab-pane label="修改" name="modified">
            <div
              v-for="item in diffResult.changes.modified"
              :key="item.key"
              style="margin: 10px 0"
            >
              <el-tag>{{ item.key }}</el-tag>
              <div style="margin-top: 5px">
                <span style="color: #f56c66">旧值: {{ JSON.stringify(item.old) }}</span>
                <br />
                <span style="color: #67c23a">新值: {{ JSON.stringify(item.new) }}</span>
              </div>
            </div>
            <el-empty v-if="!diffResult.changes.modified.length" description="无修改项" />
          </el-tab-pane>
        </el-tabs>
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
    </div>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplateVersions, rollbackTemplate } from '@/api/template'
import { getVersionDiff } from '@/api/template_version'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

const route = useRoute()
const router = useRouter()
const templateId = ref(parseInt(route.params.id))
const versions = ref([])
const selectedVersion = ref(null)
const diffResult = ref(null)
const activeTab = ref('added')
const compareDialogVisible = ref(false)
const compareVersion = ref(null)
const baseVersion = ref(null)

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
  diffResult.value = null
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
    const response = await getVersionDiff(
      templateId.value,
      baseVersion.value,
      compareVersion.value
    )
    diffResult.value = response
    compareDialogVisible.value = false
  } catch (error) {
    ElMessage.error('获取版本差异失败')
  }
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
