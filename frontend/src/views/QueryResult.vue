<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
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
        <div class="result-info">
          <p>执行时间: {{ result.execution_time_ms }}ms</p>
          <p>行数: {{ result.total }}</p>
        </div>
        <div class="export-buttons">
          <el-button @click="handleExportExcel" :loading="exportingExcel">导出 Excel</el-button>
          <el-button @click="handleExportPDF" :loading="exportingPDF">导出 PDF</el-button>
        </div>
      </el-card>
    </div>
  </Layout>
</template>

<script>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { exportExcel, exportPDF } from '@/api/report'

export default {
  name: 'QueryResult',
  components: { Layout, Header, Sidebar },
  setup() {
    const loading = ref(false)
    const exportingExcel = ref(false)
    const exportingPDF = ref(false)
    const result = ref({
      columns: [],
      rows: [],
      total: 0,
      execution_time_ms: 0
    })

    const handleExportExcel = async () => {
      if (!result.value.rows || result.value.rows.length === 0) {
        ElMessage.warning('没有查询结果可导出')
        return
      }

      exportingExcel.value = true
      try {
        const response = await exportExcel({
          data_source_id: 1, // TODO: 从路由参数获取
          sql: 'SELECT * FROM users LIMIT 10', // TODO: 从路由参数获取
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
          data_source_id: 1, // TODO: 从路由参数获取
          sql: 'SELECT * FROM users LIMIT 10', // TODO: 从路由参数获取
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

.export-buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>