<template>
  <div class="query-result">
      <el-card>
        <template #header>
          <h3>查询结果</h3>
        </template>
        <el-table :data="result.rows" v-loading="loading">
          <el-table-column
            v-for="(col, index) in result.columns"
            :key="index"
            :prop="index.toString()"
            :label="col"
          />
        </el-table>
        <div class="result-footer">
          <div class="result-info">执行时间: {{ result.execution_time_ms }}ms，共 {{ result.total }} 条记录</div>
          <el-pagination
            background
            layout="prev, pager, next, sizes, total"
            :total="result.total"
            :page-size="pageSize"
            :page-sizes="[20, 50, 100, 200]"
            :current-page="currentPage"
            @current-change="handlePageChange"
            @update:page-size="(val) => { pageSize = val; currentPage = 1 }"
          />
        </div>
        <div class="export-buttons">
          <el-button @click="handleExportExcel" :loading="exportingExcel">导出 Excel</el-button>
          <el-button @click="handleExportPDF" :loading="exportingPDF">导出 PDF</el-button>
        </div>
      </el-card>
    </div></template>

<script>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { exportExcel, exportPDF } from '@/api/report'

export default {
  name: 'QueryResult',
  props: {
    dataSourceId: {
      type: Number,
      default: null
    },
    querySql: {
      type: String,
      default: ''
    }
  },
  emits: ['re-query'],
  setup(props, { emit }) {
    const loading = ref(false)
    const exportingExcel = ref(false)
    const exportingPDF = ref(false)
    const currentPage = ref(1)
    const pageSize = ref(50)
    const result = ref({
      columns: [],
      rows: [],
      total: 0,
      page: 1,
      page_size: 50,
      execution_time_ms: 0
    })

    const handlePageChange = (page) => {
      currentPage.value = page
      emit('re-query', { page, page_size: pageSize.value })
    }

    const handleExportExcel = async () => {
      if (!result.value.rows || result.value.rows.length === 0) {
        ElMessage.warning('没有查询结果可导出')
        return
      }

      exportingExcel.value = true
      try {
        const response = await exportExcel({
          data_source_id: props.dataSourceId,
          sql: props.querySql,
          filename: `report_${Date.now()}.xlsx`
        })

        // 下载文件
        const blob = new Blob([response], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `report_${Date.now()}.xlsx`
        a.click()
        window.URL.revokeObjectURL(url)

        ElMessage.success('Excel 导出成功')
      } catch (error) {
        ElMessage.error('Excel 导出失败：' + (error.message || '未知错误'))
      } finally {
        exportingExcel.value = false
      }
    }

    const handleExportPDF = async () => {
      if (!result.value.rows || result.value.rows.length === 0) {
        ElMessage.warning('没有查询结果可导出')
        return
      }

      exportingPDF.value = true
      try {
        const response = await exportPDF({
          data_source_id: props.dataSourceId,
          sql: props.querySql,
          filename: `report_${Date.now()}.pdf`
        })

        // 下载文件
        const blob = new Blob([response], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `report_${Date.now()}.pdf`
        a.click()
        window.URL.revokeObjectURL(url)

        ElMessage.success('PDF 导出成功')
      } catch (error) {
        ElMessage.error('PDF 导出失败：' + (error.message || '未知错误'))
      } finally {
        exportingPDF.value = false
      }
    }

    return {
      loading,
      exportingExcel,
      exportingPDF,
      result,
      currentPage,
      pageSize,
      handlePageChange,
      handleExportExcel,
      handleExportPDF
    }
  }
}
</script>

<style scoped>
.query-result {
  padding: 20px;
}

.result-info {
  margin-top: 20px;
  padding: 10px;
  background: #f5f5f5;
  border-radius: 4px;
}

.result-info p {
  margin: 5px 0;
  color: #666;
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

.export-buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>