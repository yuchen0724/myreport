<template>
  <div class="dashboard-content">
    <div class="dashboard-toolbar">
      <el-button :type="isEditMode ? 'primary' : 'default'" @click="toggleEditMode">
        {{ isEditMode ? '完成编辑' : '自定义布局' }}
      </el-button>
      <el-button v-if="isEditMode" type="success" @click="saveLayout" :loading="saving">
        保存布局
      </el-button>
      <el-button v-if="isEditMode" @click="resetLayout">重置</el-button>
    </div>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      @close="error = ''"
    />

    <div v-else-if="!isEditMode" class="widget-grid">
      <div
        v-for="w in visibleWidgets"
        :key="w.widget_type"
        class="widget-grid-item"
        :class="'widget-' + w.widget_type"
      >
        <DashboardWidget :widget="w" :dashboard-data="dashboardData" />
      </div>
    </div>

    <div v-else class="edit-mode">
      <p class="edit-hint">拖拽手柄调整顺序，点击眼睛图标切换显隐</p>

      <draggable
        v-model="editingWidgets"
        item-key="widget_type"
        handle=".drag-handle"
        :animation="200"
        ghost-class="ghost"
      >
        <template #item="{ element, index }">
          <div class="edit-item">
            <div class="drag-handle">
              <el-icon><Sort /></el-icon>
            </div>
            <div class="edit-item-preview">
              <DashboardWidget :widget="element" :dashboard-data="dashboardData" />
            </div>
            <el-tooltip :content="element.visible ? '点击隐藏' : '点击显示'" placement="top">
              <el-button
                :icon="element.visible ? View : Hide"
                :type="element.visible ? 'warning' : 'info'"
                circle
                size="small"
                @click="toggleVisibility(index)"
              />
            </el-tooltip>
          </div>
        </template>
      </draggable>

      <div v-if="hiddenWidgetTypes.length" class="add-widget-section">
        <el-divider />
        <h4>已隐藏的组件</h4>
        <div class="hidden-widgets">
          <el-tag
            v-for="w in hiddenWidgetTypes"
            :key="w.widget_type"
            closable
            @close="addWidget(w.widget_type)"
          >
            {{ w.title }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Sort, View, Hide } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import DashboardWidget from '@/components/DashboardWidget.vue'
import { getWidgetConfig, saveWidgetConfig, getDashboardData } from '@/api/dashboard'

const ALL_WIDGET_META = {
  data_source_count: { title: '数据源', defaultVisible: true },
  query_count:       { title: '查询次数', defaultVisible: true },
  export_count:      { title: '导出次数', defaultVisible: true },
  template_count:    { title: '模板数量', defaultVisible: true },
  recent_queries:    { title: '最近查询', defaultVisible: true },
  recent_templates:  { title: '最近模板', defaultVisible: true },
}

export default {
  name: 'Dashboard',
  components: { DashboardWidget, draggable },
  setup() {
    const isEditMode = ref(false)
    const loading = ref(true)
    const error = ref('')
    const saving = ref(false)

    const widgets = ref([])
    const dashboardData = ref({
      data_source_count: 0,
      query_count: 0,
      export_count: 0,
      template_count: 0,
      recent_queries: [],
      recent_templates: [],
    })

    const visibleWidgets = computed(() =>
      widgets.value.filter(w => w.visible)
    )

    const editingWidgets = ref([])

    const hiddenWidgetTypes = computed(() =>
      Object.entries(ALL_WIDGET_META)
        .filter(([type]) => !editingWidgets.value.some(w => w.widget_type === type))
        .map(([widget_type, meta]) => ({ widget_type, title: meta.title }))
    )

    const loadData = async () => {
      loading.value = true
      error.value = ''
      try {
        const [configs, data] = await Promise.all([
          getWidgetConfig(),
          getDashboardData(),
        ])
        widgets.value = configs
        dashboardData.value = data
      } catch (err) {
        console.error('加载仪表盘失败:', err)
        error.value = '加载仪表盘数据失败，请稍后重试'
      } finally {
        loading.value = false
      }
    }

    const toggleEditMode = () => {
      if (isEditMode.value) {
        isEditMode.value = false
      } else {
        editingWidgets.value = widgets.value.map(w => ({ ...w }))
        isEditMode.value = true
      }
    }

    const toggleVisibility = (index) => {
      editingWidgets.value[index].visible = !editingWidgets.value[index].visible
    }

    const addWidget = (widgetType) => {
      const meta = ALL_WIDGET_META[widgetType]
      editingWidgets.value.push({
        widget_type: widgetType,
        title: meta.title,
        position: editingWidgets.value.length,
        visible: true,
      })
    }

    const saveLayout = async () => {
      saving.value = true
      try {
        const payload = {
          widgets: editingWidgets.value.map((w, i) => ({
            widget_type: w.widget_type,
            title: w.title,
            visible: w.visible,
          }))
        }
        const saved = await saveWidgetConfig(payload)
        widgets.value = saved
        isEditMode.value = false
        ElMessage.success('布局已保存')
      } catch (err) {
        console.error('保存布局失败:', err)
        ElMessage.error('保存布局失败')
      } finally {
        saving.value = false
      }
    }

    const resetLayout = () => {
      ElMessageBox.confirm('重置将恢复默认布局，确定吗？', '确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }).then(() => {
        editingWidgets.value = Object.entries(ALL_WIDGET_META).map(([widget_type, meta], i) => ({
          widget_type,
          title: meta.title,
          position: i,
          visible: meta.defaultVisible,
        }))
        ElMessage.info('已恢复默认布局，点击"保存布局"生效')
      }).catch(() => {})
    }

    onMounted(() => {
      loadData()
    })

    return {
      isEditMode, loading, error, saving,
      widgets, dashboardData, visibleWidgets, editingWidgets, hiddenWidgetTypes,
      toggleEditMode, toggleVisibility, addWidget, saveLayout, resetLayout,
    }
  }
}
</script>

<style scoped>
.dashboard-content {
  padding: 20px;
}
.dashboard-toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
.loading-container {
  padding: 40px;
}

.widget-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}
.widget-grid-item {
  flex: 0 0 auto;
}
.widget-grid-item.widget-data_source_count,
.widget-grid-item.widget-query_count,
.widget-grid-item.widget-export_count,
.widget-grid-item.widget-template_count {
  width: calc(25% - 15px);
  min-width: 200px;
}
.widget-grid-item.widget-recent_queries,
.widget-grid-item.widget-recent_templates {
  width: calc(50% - 10px);
  min-width: 300px;
}

@media (max-width: 900px) {
  .widget-grid-item.widget-data_source_count,
  .widget-grid-item.widget-query_count,
  .widget-grid-item.widget-export_count,
  .widget-grid-item.widget-template_count {
    width: calc(50% - 10px);
  }
  .widget-grid-item.widget-recent_queries,
  .widget-grid-item.widget-recent_templates {
    width: 100%;
  }
}
@media (max-width: 500px) {
  .widget-grid-item.widget-data_source_count,
  .widget-grid-item.widget-query_count,
  .widget-grid-item.widget-export_count,
  .widget-grid-item.widget-template_count {
    width: 100%;
  }
}

.edit-mode {
  max-width: 800px;
}
.edit-hint {
  color: #999;
  font-size: 13px;
  margin-bottom: 16px;
}
.edit-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  transition: box-shadow 0.2s;
}
.edit-item:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.drag-handle {
  cursor: grab;
  color: #999;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.drag-handle:active {
  cursor: grabbing;
}
.edit-item-preview {
  flex: 1;
  min-width: 0;
  pointer-events: none;
}
.ghost {
  opacity: 0.4;
  border: 2px dashed #409eff;
}
.add-widget-section {
  margin-top: 20px;
}
.hidden-widgets {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
</style>
