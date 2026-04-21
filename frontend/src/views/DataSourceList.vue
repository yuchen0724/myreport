<template>
  <Layout>
    <template #header>
      <Header />
    </template>
    <template #sidebar>
      <Sidebar />
    </template>
    <div class="datasource-list">
      <div class="toolbar">
        <el-button type="primary" @click="handleCreate">新建数据源</el-button>
      </div>
      <el-table :data="dataSources" v-loading="loading">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="type" label="类型" />
        <el-table-column prop="host" label="主机" />
        <el-table-column prop="port" label="端口" />
        <el-table-column prop="database" label="数据库" />
        <el-table-column prop="is_active" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </Layout>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import Layout from '@/components/Layout.vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { getDataSourceList, deleteDataSource } from '@/api/data_source'

export default {
  name: 'DataSourceList',
  components: { Layout, Header, Sidebar },
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const dataSources = ref([])

    const loadDataSources = async () => {
      loading.value = true
      try {
        dataSources.value = await getDataSourceList()
      } catch (error) {
        ElMessage.error('加载数据源失败')
      } finally {
        loading.value = false
      }
    }

    const handleCreate = () => {
      router.push('/datasources/create')
    }

    const handleEdit = (row) => {
      router.push()
    }

    const handleDelete = async (row) => {
      try {
        await ElMessageBox.confirm('确定要删除该数据源吗？', '提示', {
          type: 'warning'
        })
        await deleteDataSource(row.id)
        ElMessage.success('删除成功')
        loadDataSources()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
    }

    onMounted(() => {
      loadDataSources()
    })

    return {
      loading,
      dataSources,
      handleCreate,
      handleEdit,
      handleDelete
    }
  }
}
</script>

<style scoped>
.datasource-list {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
}
</style>