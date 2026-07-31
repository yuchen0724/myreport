<template>
  <div class="design-studio">
    <header class="hero">
      <div>
        <span class="eyebrow">GOVERNED AI DESIGN</span>
        <h1>报表与指标设计工作台</h1>
        <p>AI 负责生成草稿和解释风险，发布动作始终由你确认。</p>
      </div>
      <el-select v-model="dataSourceId" placeholder="选择数据源" filterable class="source-select">
        <el-option v-for="source in dataSources" :key="source.id" :label="source.name" :value="source.id" />
      </el-select>
    </header>

    <el-tabs v-model="activeTab" class="studio-tabs">
      <el-tab-pane label="报表搭建" name="report">
        <section class="workspace-grid">
          <el-card shadow="never" class="input-card">
            <h3>描述你想看的报表</h3>
            <el-input v-model="reportRequirement" type="textarea" :rows="7" placeholder="例如：按门店查看最近 30 天销售额和毛利率趋势，并标记环比下降门店" />
            <el-select v-model="preferredChart" class="full-width" placeholder="图表偏好">
              <el-option label="自动选择" value="" />
              <el-option label="表格" value="table" />
              <el-option label="折线图" value="line" />
              <el-option label="柱状图" value="bar" />
            </el-select>
            <el-button type="primary" :loading="reportLoading" @click="createReportDraft">生成草稿</el-button>
          </el-card>
          <el-card shadow="never" class="result-card">
            <template #header><b>可审核草稿</b></template>
            <el-empty v-if="!reportDraft" description="先描述报表需求" />
            <template v-else>
              <h3>{{ reportDraft.template.name }}</h3>
              <p>{{ reportDraft.template.description }}</p>
              <pre class="code-block">{{ reportDraft.template.config.sql || '尚未生成安全 SQL' }}</pre>
              <el-alert v-for="warning in reportDraft.warnings" :key="warning" :title="warning" type="warning" :closable="false" class="notice" />
              <el-button type="success" :disabled="!reportDraft.template.config.sql" @click="saveReportDraft">确认并保存为模板</el-button>
            </template>
          </el-card>
        </section>
      </el-tab-pane>

      <el-tab-pane label="指标治理" name="metric">
        <section class="workspace-grid">
          <el-card shadow="never" class="input-card">
            <h3>指标体检</h3>
            <p>检查重复定义、说明缺失、无下钻维度和库存快照风险。</p>
            <el-button type="primary" :loading="auditLoading" @click="runMetricAudit">开始体检</el-button>
            <el-divider />
            <h3>生成指标草稿</h3>
            <el-input v-model="metricRequirement" type="textarea" :rows="5" placeholder="描述指标名称、业务口径、来源字段和时间维度" />
            <el-button type="primary" :loading="metricLoading" @click="createMetricDraft">生成指标草稿</el-button>
          </el-card>
          <el-card shadow="never" class="result-card">
            <template #header><b>治理结果</b></template>
            <el-descriptions v-if="auditResult" :column="3" border>
              <el-descriptions-item label="指标数">{{ auditResult.metric_count }}</el-descriptions-item>
              <el-descriptions-item label="问题数">{{ auditResult.finding_count }}</el-descriptions-item>
              <el-descriptions-item label="发布门禁">{{ auditResult.release_gate }}</el-descriptions-item>
            </el-descriptions>
            <el-table v-if="auditResult?.findings?.length" :data="auditResult.findings" size="small" class="audit-table">
              <el-table-column prop="metric_key" label="指标" width="160" />
              <el-table-column prop="severity" label="风险" width="80" />
              <el-table-column prop="message" label="发现" />
            </el-table>
            <template v-if="metricDraft">
              <el-divider />
              <pre class="code-block">{{ JSON.stringify(metricDraft.draft, null, 2) }}</pre>
              <el-alert v-for="warning in metricDraft.warnings" :key="warning" :title="warning" type="warning" :closable="false" class="notice" />
              <el-button type="success" :disabled="!metricDraft.draft || metricDraft.warnings.length > 0" @click="saveMetricDraft">确认并保存为停用指标</el-button>
            </template>
          </el-card>
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { auditMetrics, generateMetricDraft, generateReportDraft } from '@/api/aiDesign'
import { getDataSourceList } from '@/api/data_source'
import { createTemplate } from '@/api/template'
import { createSemanticMetric } from '@/api/semanticMetric'

const activeTab = ref('report')
const dataSources = ref([])
const dataSourceId = ref(null)
const reportRequirement = ref('')
const preferredChart = ref('')
const reportDraft = ref(null)
const reportLoading = ref(false)
const auditResult = ref(null)
const auditLoading = ref(false)
const metricRequirement = ref('')
const metricDraft = ref(null)
const metricLoading = ref(false)

onMounted(async () => {
  dataSources.value = await getDataSourceList()
  dataSourceId.value = dataSources.value[0]?.id || null
})

function ensureReady(requirement = '') {
  if (!dataSourceId.value) return ElMessage.warning('请先选择数据源')
  if (requirement && requirement.trim().length < 3) return ElMessage.warning('请补充更具体的需求')
  return true
}

async function createReportDraft() {
  if (!ensureReady(reportRequirement.value)) return
  reportLoading.value = true
  try {
    reportDraft.value = await generateReportDraft({ data_source_id: dataSourceId.value, requirement: reportRequirement.value, preferred_chart: preferredChart.value || undefined })
  } finally { reportLoading.value = false }
}

async function saveReportDraft() {
  await ElMessageBox.confirm('确认将当前草稿保存为私有模板？', '发布确认')
  await createTemplate(reportDraft.value.template)
  ElMessage.success('报表模板已保存')
}

async function runMetricAudit() {
  if (!ensureReady()) return
  auditLoading.value = true
  try { auditResult.value = await auditMetrics(dataSourceId.value) } finally { auditLoading.value = false }
}

async function createMetricDraft() {
  if (!ensureReady(metricRequirement.value)) return
  metricLoading.value = true
  try { metricDraft.value = await generateMetricDraft({ data_source_id: dataSourceId.value, requirement: metricRequirement.value }) } finally { metricLoading.value = false }
}

async function saveMetricDraft() {
  await ElMessageBox.confirm('确认保存为停用指标？完成数据验证后再手工启用。', '治理确认')
  await createSemanticMetric({ ...metricDraft.value.draft, is_active: false })
  ElMessage.success('指标草稿已保存为停用状态')
}
</script>

<style scoped>
.design-studio { padding: 24px; background: radial-gradient(circle at 80% 0, #d8efe8 0, transparent 34%), #f6f3eb; min-height: calc(100vh - 48px); }
.hero { display: flex; justify-content: space-between; align-items: end; gap: 24px; margin-bottom: 22px; }
.eyebrow { color: #16705a; font-size: 12px; font-weight: 800; letter-spacing: .16em; }
.hero h1 { margin: 7px 0; font-family: Georgia, serif; font-size: clamp(28px, 4vw, 46px); color: #173c35; }
.hero p { margin: 0; color: #5d6863; }
.source-select { width: 280px; }
.studio-tabs { background: rgba(255,255,255,.72); border: 1px solid #d9ded8; border-radius: 16px; padding: 12px 20px 20px; }
.workspace-grid { display: grid; grid-template-columns: minmax(300px, .8fr) minmax(420px, 1.2fr); gap: 18px; }
.input-card, .result-card { border-radius: 12px; }
.input-card :deep(.el-textarea), .full-width { width: 100%; margin-bottom: 14px; }
.code-block { max-height: 320px; overflow: auto; padding: 14px; background: #172522; color: #d9f1e9; border-radius: 9px; white-space: pre-wrap; }
.notice { margin: 8px 0; }
.audit-table { margin-top: 14px; }
@media (max-width: 860px) { .hero { align-items: stretch; flex-direction: column; } .source-select { width: 100%; } .workspace-grid { grid-template-columns: 1fr; } }
</style>
