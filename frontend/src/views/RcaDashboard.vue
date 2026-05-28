<template>
  <div class="rca-dashboard">
    <!-- 新建分析 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>新建分析</span>
          <el-button type="primary" @click="showConfigDialog = true">指标配置</el-button>
        </div>
      </template>

      <el-form :model="analyzeForm" label-width="80px" inline>
        <el-form-item label="指标">
          <el-select v-model="analyzeForm.metric_config_id" placeholder="选择指标" style="width: 200px">
            <el-option
              v-for="c in configs"
              :key="c.id"
              :label="c.label"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="分析日期">
          <el-date-picker
            v-model="analyzeForm.analysis_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="对比周期">
          <el-select v-model="analyzeForm.period_days" style="width: 100px">
            <el-option :value="7" label="7天" />
            <el-option :value="14" label="14天" />
            <el-option :value="30" label="30天" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="analyzing" @click="handleAnalyze">
            开始分析
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 分析历史 -->
    <el-card>
      <template #header><span>分析历史</span></template>

      <el-table :data="tasks" v-loading="loadingTasks" style="width: 100%">
        <el-table-column prop="task_id" label="任务ID" width="280" show-overflow-tooltip />
        <el-table-column label="指标" width="150">
          <template #default="{ row }">
            {{ getConfigLabel(row.metric_config_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="analysis_date" label="分析日期" width="120" />
        <el-table-column prop="period_days" label="周期" width="80">
          <template #default="{ row }">{{ row.period_days }}天</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'"
              size="small"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="异常数" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.anomaly_count" type="danger" size="small">{{ row.anomaly_count }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="总体变化" width="100">
          <template #default="{ row }">
            <span v-if="row.summary && row.summary.total_change_pct != null"
                  :class="row.summary.total_change_pct < 0 ? 'text-danger' : 'text-success'">
              {{ row.summary.total_change_pct }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'completed'"
              type="primary"
              link
              size="small"
              @click="$router.push(`/rca/${row.task_id}`)"
            >
              查看异常
            </el-button>
            <el-popconfirm title="确认删除此分析记录?" @confirm="handleDeleteTask(row.task_id)">
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 配置管理弹窗 -->
    <el-dialog v-model="showConfigDialog" title="指标配置管理" width="960px" :style="{ maxHeight: '80vh' }" class="config-dialog">
      <div class="config-dialog-body">
      <el-button type="primary" size="small" style="margin-bottom: 12px" @click="showAddConfig = true">
        新增配置
      </el-button>
      <el-table :data="configs" style="width: 100%" :max-height="320">
        <el-table-column prop="label" label="指标名" width="100" />
        <el-table-column prop="metric_field" label="字段" min-width="180" show-overflow-tooltip />
        <el-table-column prop="source_table" label="数据表" min-width="220" show-overflow-tooltip />
        <el-table-column prop="threshold_value" label="阈值" width="70" />
        <el-table-column prop="compare_type" label="对比方式" width="80" />
        <el-table-column label="下钻维度" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="d in row.drill_dimensions" :key="d" size="small" style="margin: 2px">{{ d }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEditConfig(row)">编辑</el-button>
            <el-popconfirm title="确认删除?" @confirm="handleDeleteConfig(row.id)">
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增配置表单 -->
      <el-collapse-transition>
        <el-form
          v-if="showAddConfig"
          :model="newConfig"
          label-width="80px"
          style="margin-top: 16px; border-top: 1px solid #eee; padding-top: 16px"
        >
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="指标名">
                <el-input v-model="newConfig.label" placeholder="如: 实销金额" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="字段名">
                <el-input v-model="newConfig.metric_field" placeholder="如: actual_sale_untaxed_amt" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="阈值">
                <el-input-number v-model="newConfig.threshold_value" :min="1" :max="100" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="数据表">
                <el-input v-model="newConfig.source_table" placeholder="Doris 全表名" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="集团ID">
                <el-input-number v-model="newConfig.group_id" :min="1" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="数据源">
                <el-input-number v-model="newConfig.data_source_id" :min="1" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item>
            <el-button type="primary" @click="handleAddConfig">保存</el-button>
            <el-button @click="showAddConfig = false">取消</el-button>
          </el-form-item>
        </el-form>
      </el-collapse-transition>

      <!-- 编辑配置表单 -->
      <el-collapse-transition>
        <el-form
          v-if="editingConfig"
          :model="editingConfig"
          label-width="80px"
          style="margin-top: 16px; border-top: 1px solid #eee; padding-top: 16px"
        >
          <h4 style="margin: 0 0 12px">编辑: {{ editingConfig.label }}</h4>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="指标名">
                <el-input v-model="editingConfig.label" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="字段名">
                <el-input v-model="editingConfig.metric_field" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="阈值">
                <el-input-number v-model="editingConfig.threshold_value" :min="1" :max="100" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="数据表">
                <el-input v-model="editingConfig.source_table" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="集团ID">
                <el-input-number v-model="editingConfig.group_id" :min="1" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="数据源">
                <el-input-number v-model="editingConfig.data_source_id" :min="1" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="下钻维度">
            <el-select v-model="editingConfig.drill_dimensions" multiple style="width: 100%">
              <el-option label="营运类目1级" value="operation_category1_name" />
              <el-option label="营运类目2级" value="operation_category2_name" />
              <el-option label="采销类目1级" value="purchase_category1_name" />
              <el-option label="门店" value="store_code" />
              <el-option label="商品" value="matnr" />
              <el-option label="供应商" value="supplier_name" />
              <el-option label="品牌" value="brand_flag" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleUpdateConfig">保存修改</el-button>
            <el-button @click="editingConfig = null">取消</el-button>
          </el-form-item>
        </el-form>
      </el-collapse-transition>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getRcaConfigs, createRcaConfig, updateRcaConfig, deleteRcaConfig,
  getRcaTasks, deleteRcaTask, triggerRcaAnalyze
} from '@/api/rca'

const configs = ref([])
const tasks = ref([])
const loadingTasks = ref(false)
const analyzing = ref(false)
const showConfigDialog = ref(false)
const showAddConfig = ref(false)
const editingConfig = ref(null)  // 编辑中的配置

const analyzeForm = ref({
  metric_config_id: null,
  analysis_date: new Date().toISOString().slice(0, 10),
  period_days: 7,
})

const newConfig = ref({
  name: '',
  label: '',
  metric_field: '',
  source_table: '',
  threshold_type: 'percent_change',
  threshold_value: 10,
  compare_type: 'mom',
  drill_dimensions: ['operation_category1_name', 'store_code', 'matnr'],
  group_id: 123,
  data_source_id: 1,
})

const getConfigLabel = (id) => {
  const c = configs.value.find(x => x.id === id)
  return c ? c.label : id
}

const loadData = async () => {
  try {
    const [cfgRes, taskRes] = await Promise.all([getRcaConfigs(), getRcaTasks()])
    configs.value = cfgRes.data || cfgRes
    tasks.value = taskRes.data || taskRes
  } catch (e) {
    console.error('Load RCA data failed:', e)
  }
}

const handleAnalyze = async () => {
  if (!analyzeForm.value.metric_config_id) {
    ElMessage.warning('请选择指标')
    return
  }
  analyzing.value = true
  try {
    await triggerRcaAnalyze(analyzeForm.value)
    ElMessage.success('分析完成')
    await loadData()
  } catch (e) {
    ElMessage.error('分析失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    analyzing.value = false
  }
}

const handleAddConfig = async () => {
  const cfg = { ...newConfig.value }
  cfg.name = cfg.label // 用 label 作为 name
  try {
    await createRcaConfig(cfg)
    ElMessage.success('配置已创建')
    showAddConfig.value = false
    await loadData()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  }
}

const handleEditConfig = (row) => {
  editingConfig.value = { ...row }
  showAddConfig.value = false
}

const handleUpdateConfig = async () => {
  const cfg = { ...editingConfig.value }
  cfg.name = cfg.label
  try {
    await updateRcaConfig(cfg.id, cfg)
    ElMessage.success('配置已更新')
    editingConfig.value = null
    await loadData()
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
  }
}

const handleDeleteConfig = async (id) => {
  try {
    await deleteRcaConfig(id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const handleDeleteTask = async (taskId) => {
  try {
    await deleteRcaTask(taskId)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.rca-dashboard {
  padding: 16px;
}
.text-danger {
  color: #f56c6c;
  font-weight: bold;
}
.text-success {
  color: #67c23a;
  font-weight: bold;
}
</style>
<style>
.config-dialog .el-dialog__body {
  max-height: 70vh;
  overflow-y: auto;
  padding: 16px 20px;
}
.config-dialog-body {
  min-height: 200px;
}
</style>
