<template>
  <div class="report-view">
    <el-card v-loading="loading">
      
        <div class="card-header">
          <div class="title-section">
            <span class="title">{{ menuInfo?.name || '报表' }}</span>
            <el-tag v-if="templateInfo" type="info" size="small">
              {{ templateInfo.name }}
            </el-tag>
          </div>
          <div class="actions">
            <el-button @click="handleExport('excel')" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出 Excel
            </el-button>
            <el-button @click="handleExport('pdf')" :loading="exporting">
              <el-icon><Document /></el-icon>
              导出 PDF
            </el-button>
          </div>
        </div>
      

      <!-- 查询条件区域 -->
      <div v-if="templateInfo" class="params-section">
        <el-form :model="params" inline class="params-form">
          <el-form-item
            v-for="param in templateParams"
            :key="param.name"
            :label="param.label || param.name"
          >
            <el-input
              v-if="param.type === 'string'"
              v-model="params[param.name]"
              :placeholder="'请输入' + (param.label || param.name)"
              style="width: 200px"
            />
            <el-input-number
              v-else-if="param.type === 'number'"
              v-model="params[param.name]"
              :placeholder="'请输入' + (param.label || param.name)"
            />
            <el-date-picker
              v-else-if="param.type === 'date'"
              v-model="params[param.name]"
              type="date"
              :placeholder="'请选择' + (param.label || param.name)"
            />
            <el-date-picker
              v-else-if="param.type === 'daterange'"
              v-model="params[param.name]"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadData">
              <el-icon><Search /></el-icon>
              查询
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 数据表格工具栏 -->
      <div v-if="data.length > 0" class="table-toolbar">
        <el-popover
          placement="bottom-start"
          :width="200"
          trigger="click"
        >
          <template #reference>
            <el-button size="small">
              <el-icon><Grid /></el-icon>
              列展示
            </el-button>
          </template>
          <div class="column-visibility">
            <el-checkbox
              v-model="checkAllColumns"
              :indeterminate="isIndeterminate"
              @change="handleCheckAllColumns"
            >
              全选
            </el-checkbox>
            <el-checkbox-group v-model="visibleColumns" @change="handleCheckedColumns">
              <el-checkbox
                v-for="col in columns"
                :key="col"
                :label="col"
                :value="col"
              >
                {{ col }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </el-popover>
        
        <el-input
          v-model="searchText"
          placeholder="搜索表格数据..."
          clearable
          size="small"
          style="width: 200px; margin-left: 10px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- 数据表格 -->
      <el-table
        v-if="filteredData.length > 0"
        :data="paginatedData"
        border
        stripe
        :default-sort="{ prop: sortProp, order: sortOrder }"
        @sort-change="handleSortChange"
        max-height="500"
        style="width: 100%"
      >
        <el-table-column
          v-for="col in visibleColumns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="120"
          show-overflow-tooltip
          sortable="custom"
        />
      </el-table>

      <!-- 空状态 -->
      <el-empty v-else-if="!loading" description="暂无数据，请设置查询参数后点击查询" />

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, Document, Search, Grid } from '@element-plus/icons-vue'
import { getMenus, getMenuWithTemplate } from '@/api/menu'
import { executeQuery } from '@/api/query'
import { exportExcel, exportPDF } from '@/api/report'

const route = useRoute()
const loading = ref(false)
const exporting = ref(false)
const menuInfo = ref(null)
const templateInfo = ref(null)
const data = ref([])
const columns = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const params = reactive({})
const templateParams = ref([])

// 表格增强功能
const searchText = ref('')
const visibleColumns = ref([])
const checkAllColumns = ref(true)
const isIndeterminate = ref(false)
const sortProp = ref('')
const sortOrder = ref(null)

// 初始化可见列
watch(columns, (newCols) => {
  visibleColumns.value = [...newCols]
}, { immediate: true })

// 筛选数据
const filteredData = computed(() => {
  if (!searchText.value) return data.value
  const keyword = searchText.value.toLowerCase()
  return data.value.filter(row => {
    return Object.values(row).some(val => 
      String(val).toLowerCase().includes(keyword)
    )
  })
})

// 分页数据
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredData.value.slice(start, end)
})

// 更新总数
watch(filteredData, (newData) => {
  total.value = newData.length
  currentPage.value = 1  // 筛选后回到第一页
})

// 列展示控制
const handleCheckAllColumns = (val) => {
  visibleColumns.value = val ? [...columns.value] : []
  isIndeterminate.value = false
}

const handleCheckedColumns = (value) => {
  const checkedCount = value.length
  checkAllColumns.value = checkedCount === columns.value.length
  isIndeterminate.value = checkedCount > 0 && checkedCount < columns.value.length
}

// 排序处理
const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop
  sortOrder.value = order
  if (!prop || !order) {
    // 取消排序，恢复原始顺序
    return
  }
  const multiplier = order === 'ascending' ? 1 : -1
  data.value.sort((a, b) => {
    const valA = a[prop]
    const valB = b[prop]
    if (valA === valB) return 0
    if (valA === null || valA === undefined) return 1
    if (valB === null || valB === undefined) return -1
    if (typeof valA === 'number' && typeof valB === 'number') {
      return (valA - valB) * multiplier
    }
    return String(valA).localeCompare(String(valB)) * multiplier
  })
}

// 通过 path 查找菜单（当路由参数不是数字ID时）
const findMenuIdByPath = async (path) => {
  try {
    const menus = await getMenus({ skip: 0, limit: 1000 })
    const menuList = Array.isArray(menus) ? menus : (menus.data || [])
    const matched = menuList.find(m => m.path === path)
    return matched ? matched.id : null
  } catch {
    return null
  }
}

// 加载菜单和模板信息
const loadMenuInfo = async () => {
  let menuId = route.params.id
  if (!menuId) {
    ElMessage.error('缺少菜单ID')
    return
  }

  try {
    loading.value = true

    // 如果路由参数不是纯数字（如 /report/sales），先按 path 查找菜单
    if (!/^\d+$/.test(menuId)) {
      const resolvedId = await findMenuIdByPath('/report/' + menuId)
      if (resolvedId) {
        menuId = resolvedId
      } else {
        ElMessage.error('未找到对应菜单')
        return
      }
    }

    const res = await getMenuWithTemplate(menuId)
    menuInfo.value = res
    templateInfo.value = res.template

    // 解析模板参数
    if (templateInfo.value?.config?.params) {
      templateParams.value = templateInfo.value.config.params
      // 设置默认值
      templateParams.value.forEach(p => {
        if (p.default) {
          params[p.name] = p.default
        }
      })
    }

    // 无论有无参数都等待用户主动点击查询，不自动加载数据
  } catch (error) {
    ElMessage.error('加载报表失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 构建带参数的 SQL
const buildSqlWithParams = () => {
  const config = templateInfo.value?.config
  if (!config?.sql) return ''
  let sql = config.sql
  Object.entries(params).forEach(([key, value]) => {
    let replaceValue = value
    // 处理 Date 对象，转换为 YYYYMMDD 格式
    if (value instanceof Date) {
      const year = value.getFullYear()
      const month = String(value.getMonth() + 1).padStart(2, '0')
      const day = String(value.getDate()).padStart(2, '0')
      replaceValue = `${year}${month}${day}`
    }
    // 处理日期范围数组 [startDate, endDate]
    else if (Array.isArray(value) && value[0] instanceof Date) {
      replaceValue = value.map(d => {
        const year = d.getFullYear()
        const month = String(d.getMonth() + 1).padStart(2, '0')
        const day = String(d.getDate()).padStart(2, '0')
        return `${year}${month}${day}`
      }).join(',')
    }
    sql = sql.replace(new RegExp(`\\$\\{${key}\\}|:${key}`, 'g'), replaceValue ?? '')
  })
  return sql
}

// 加载数据
const loadData = async () => {
  if (!templateInfo.value) {
    ElMessage.warning('未关联报表模板')
    return
  }

  const config = templateInfo.value.config
  if (!config) {
    ElMessage.error('模板缺少配置信息')
    return
  }
  if (!config.data_source_id) {
    ElMessage.error('模板缺少数据源配置')
    return
  }
  if (!config.sql) {
    ElMessage.error('模板缺少 SQL 配置')
    return
  }

  try {
    loading.value = true
    const res = await executeQuery({
      data_source_id: config.data_source_id,
      sql: buildSqlWithParams(),
      params: {},  // 前端已替换占位符，后端无需再处理
      page: currentPage.value,
      page_size: Math.min(pageSize.value, 5000)  // 限制最大返回5000条
    })

    // executeQuery 调用 /api/query/sql，返回 SQLQueryResponse { columns, rows, total, ... }
    // rows 是二维数组 [[val1, val2], ...]，需转换为对象数组适配 el-table
    const cols = res.columns || []
    const rawRows = res.rows || []
    data.value = rawRows.map(row => {
      const obj = {}
      cols.forEach((col, i) => { obj[col] = row[i] })
      return obj
    })
    columns.value = cols
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error('查询失败：' + (error.response?.data?.detail || error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 分页变化时重新请求后端
const handlePageChange = () => {
  loadData()
}

// 导出
const handleExport = async (format) => {
  if (!templateInfo.value) {
    ElMessage.warning('未关联报表模板')
    return
  }

  try {
    exporting.value = true
    
    const config = templateInfo.value.config
    const sql = buildSqlWithParams()

    // 使用异步导出 API
    const exportFn = format === 'pdf' ? exportPDF : exportExcel
    const res = await exportFn({
      data_source_id: config.data_source_id,
      sql: sql
    })

    // 轮询任务状态
    const taskId = res?.task_id
    if (!taskId) {
      ElMessage.error('导出任务创建失败')
      return
    }

    // 轮询等待导出完成
    let taskStatus = 'pending'
    let maxAttempts = 60 // 最多等待 60 秒
    
    while (taskStatus === 'pending' || taskStatus === 'processing') {
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      const statusRes = await import('@/api/report').then(m => m.getExportTask(taskId))
      taskStatus = statusRes?.status
      
      maxAttempts--
      if (maxAttempts <= 0) {
        ElMessage.warning('导出超时，请稍后���看任务状态')
        break
      }
    }

    if (taskStatus === 'completed') {
      // 下载文件
      const fileRes = await import('@/api/report').then(m => m.downloadExportFile(taskId))
      const blob = new Blob([fileRes], { 
        type: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${menuInfo.value.name || 'report'}.${format === 'pdf' ? 'pdf' : 'xlsx'}`
      a.click()
      window.URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    } else {
      ElMessage.error('导出失败，任务状态：' + taskStatus)
    }
  } catch (error) {
    ElMessage.error('导出失败：' + (error.response?.data?.detail || error.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}

// 监听路由变化
watch(() => route.params.id, (newId) => {
  if (newId) {
    loadMenuInfo()
  }
})

onMounted(() => {
  if (route.params.id) {
    loadMenuInfo()
  }
})
</script>

<style scoped>
.report-view {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.params-section {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.params-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>