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
      </el-card>
    </div>
  </Layout>
</template>

<script>
import { ref } from 'vue'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'

export default {
  name: 'QueryResult',
  components: { Layout, Header, Sidebar },
  setup() {
    const loading = ref(false)
    const result = ref({
      columns: [],
      rows: [],
      total: 0,
      execution_time_ms: 0
    })

    return {
      loading,
      result
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
</style>