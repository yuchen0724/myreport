<template>
  <div class="sql-analysis-panel">
    <el-card shadow="never" class="analysis-card">
      <template #header>
        <div class="card-header">
          <span class="title">SQL 复杂度分析</span>
          <div class="header-actions">
            <el-button
              type="primary"
              size="small"
              :loading="analyzing"
              @click="doAnalyze"
            >
              <el-icon><Search /></el-icon>
              分析 SQL
            </el-button>
            <el-button
              size="small"
              @click="saveResult"
              :disabled="!result"
            >
              <el-icon><Download /></el-icon>
              保存
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!result" class="empty-state">
        <el-empty description="点击「分析 SQL」按钮开始分析" :image-size="80" />
      </div>

      <div v-else class="analysis-result">
        <!-- 复杂度评分 -->
        <div class="score-section">
          <div class="score-display">
            <el-progress
              type="dashboard"
              :percentage="result.complexity_score"
              :color="scoreColor"
              :width="120"
            >
              <template #default="{ percentage }">
                <div class="score-text">
                  <span class="score-value">{{ percentage }}</span>
                  <span class="score-label">复杂度评分</span>
                </div>
              </template>
            </el-progress>
          </div>
          <div class="level-badge">
            <el-tag :type="levelType" effect="dark" size="large">
              {{ levelLabel }}
            </el-tag>
          </div>
        </div>

        <!-- 详细指标 -->
        <div class="metrics-grid">
          <div class="metric-item" v-for="(value, key) in metricLabels" :key="key">
            <span class="metric-label">{{ value.label }}</span>
            <span class="metric-value">{{ result.metrics[key] }}</span>
          </div>
        </div>

        <!-- 预估耗时 -->
        <div v-if="result.estimated_time_ms" class="estimate-section">
          <el-icon class="estimate-icon"><Clock /></el-icon>
          <span>预估执行时间: {{ formatTime(result.estimated_time_ms) }}</span>
        </div>

        <!-- 检测到的问题 -->
        <div v-if="result.issues && result.issues.length" class="issues-section">
          <h4 class="section-title">
            <el-icon><WarningFilled /></el-icon>
            检测到的问题 ({{ result.issues.length }})
          </h4>
          <div
            class="issue-item"
            v-for="(issue, idx) in result.issues"
            :key="idx"
            :class="`issue-${issue.severity}`"
          >
            <el-tag :type="severityType(issue.severity)" size="small">
              {{ severityLabel(issue.severity) }}
            </el-tag>
            <div class="issue-content">
              <span class="issue-position">{{ issue.position }}</span>
              <span class="issue-desc">{{ issue.description }}</span>
            </div>
          </div>
        </div>

        <!-- 优化建议 -->
        <div v-if="result.suggestions && result.suggestions.length" class="suggestions-section">
          <h4 class="section-title">
            <el-icon><Lightning /></el-icon>
            优化建议 ({{ result.suggestions.length }})
          </h4>
          <div
            class="suggestion-item"
            v-for="(suggestion, idx) in result.suggestions"
            :key="idx"
          >
            <el-tag type="success" size="small">{{ suggestion.action }}</el-tag>
            <div class="suggestion-content">
              <span class="suggestion-field">{{ suggestion.field }}</span>
              <span class="suggestion-desc">{{ suggestion.description }}</span>
            </div>
          </div>
        </div>

        <!-- 无问题/无建议 -->
        <div v-if="!result.issues.length && !result.suggestions.length" class="no-issues">
          <el-result icon="success" title="SQL 复杂度较低，未发现明显问题" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search, Download, Clock, WarningFilled, Lightning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { analyzeSQL } from '@/api/sqlAnalysis'

const props = defineProps({
  sql: {
    type: String,
    default: ''
  }
})

const result = ref(null)
const analyzing = ref(false)

const levelLabel = computed(() => {
  if (!result.value) return ''
  const map = { low: '低', medium: '中', high: '高', critical: '严重' }
  return map[result.value.complexity_level] || result.value.complexity_level
})

const levelType = computed(() => {
  if (!result.value) return ''
  const map = { low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[result.value.complexity_level] || 'info'
})

const scoreColor = computed(() => {
  if (!result.value) return '#409eff'
  const score = result.value.complexity_score
  if (score <= 20) return '#67c23a'
  if (score <= 45) return '#e6a23c'
  if (score <= 70) return '#f56c6c'
  return '#ff0000'
})

const metricLabels = {
  select_column_count: { label: 'SELECT 列数' },
  join_count: { label: 'JOIN 数量' },
  subquery_depth: { label: '子查询深度' },
  group_by_count: { label: 'GROUP BY 字段' },
  order_by_count: { label: 'ORDER BY 字段' },
  function_call_count: { label: '函数调用' },
  where_condition_count: { label: 'WHERE 条件' },
  table_count: { label: '表数量' },
}

function severityType(severity) {
  const map = { info: 'info', warning: 'warning', critical: 'danger' }
  return map[severity] || 'info'
}

function severityLabel(severity) {
  const map = { info: '提示', warning: '警告', critical: '严重' }
  return map[severity] || severity
}

function formatTime(ms) {
  if (ms >= 60000) {
    return `${(ms / 60000).toFixed(1)} 分钟`
  }
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)} 秒`
  }
  return `${ms} ms`
}

async function doAnalyze() {
  const sql = props.sql?.trim()
  if (!sql) {
    ElMessage.warning('请输入 SQL 语句')
    return
  }
  analyzing.value = true
  try {
    const res = await analyzeSQL(sql, false)
    result.value = res
    ElMessage.success('分析完成')
  } catch (e) {
    ElMessage.error('分析失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    analyzing.value = false
  }
}

async function saveResult() {
  if (!props.sql?.trim()) return
  analyzing.value = true
  try {
    await analyzeSQL(props.sql, true)
    ElMessage.success('分析结果已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    analyzing.value = false
  }
}
</script>

<style scoped>
.sql-analysis-panel {
  margin-top: 16px;
}

.analysis-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header .title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  padding: 20px 0;
}

.analysis-result {
  padding: 4px 0;
}

/* 评分区域 */
.score-section {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 16px 0;
}

.score-display {
  flex-shrink: 0;
}

.score-text {
  text-align: center;
}

.score-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.score-label {
  font-size: 12px;
  color: #909399;
}

.level-badge {
  flex: 1;
}

/* 指标网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 12px 0;
  border-top: 1px solid #f0f0f0;
}

.metric-item {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
}

.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

/* 预估耗时 */
.estimate-section {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 6px;
  color: #409eff;
  font-size: 14px;
}

.estimate-icon {
  font-size: 16px;
}

/* 通用 section */
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 16px 0 8px;
}

/* 问题列表 */
.issue-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: #f8f9fa;
}

.issue-item.issue-critical {
  background: #fef0f0;
  border: 1px solid #fbc4c4;
}

.issue-item.issue-warning {
  background: #fdf6ec;
  border: 1px solid #faecd8;
}

.issue-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.issue-position {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.issue-desc {
  font-size: 13px;
  color: #606266;
}

/* 建议列表 */
.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
}

.suggestion-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.suggestion-field {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.suggestion-desc {
  font-size: 13px;
  color: #606266;
}

/* 无问题 */
.no-issues {
  padding: 12px 0;
}

@media (max-width: 640px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
