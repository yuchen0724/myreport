<template>
  <div class="dashboard-content">
    <!-- 顶部工具栏 -->
    <div class="dashboard-toolbar">
      <div class="toolbar-left">
        <el-breadcrumb v-if="currentLayout.id">
          <el-breadcrumb-item :to="{ name: 'Dashboard' }">仪表盘</el-breadcrumb-item>
          <el-breadcrumb-item>
            <el-select
              v-model="currentLayoutId"
              placeholder="选择布局"
              size="small"
              style="width: 200px"
              @change="switchLayout"
            >
              <el-option
                v-for="l in layouts"
                :key="l.id"
                :label="l.name + (l.is_default ? ' (默认)' : '')"
                :value="l.id"
              />
            </el-select>
          </el-breadcrumb-item>
        </el-breadcrumb>
        <span v-else class="page-title">仪表盘</span>
      </div>

      <div class="toolbar-right">
        <el-button v-if="!currentLayout.id && layouts.length > 0" type="primary" @click="createNewLayout">
          + 新建布局
        </el-button>

        <template v-if="currentLayout.id">
          <el-button :type="isEditing ? 'primary' : 'default'" @click="toggleEdit">
            {{ isEditing ? '完成编辑' : '编辑布局' }}
          </el-button>

          <el-button v-if="isEditing" type="success" @click="saveLayout" :loading="savingLayout">
            保存
          </el-button>
          <el-button v-if="isEditing" @click="showPresetDialog = true">
            预设模板
          </el-button>
          <el-button v-if="isEditing" @click="showAddPanel = !showAddPanel">
            {{ showAddPanel ? '收起面板' : '添加组件' }}
          </el-button>

          <el-button v-if="!isEditing" type="info" text @click="renameLayout">
            重命名
          </el-button>
          <el-button v-if="!isEditing" type="danger" text @click="handleDeleteLayout">
            删除
          </el-button>
        </template>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 错误 -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon closable />

    <!-- 空状态：无布局 -->
    <div v-else-if="!currentLayout.id && layouts.length === 0" class="empty-state">
      <el-empty description="还没有仪表盘布局">
        <el-button type="primary" @click="createNewLayout">创建第一个布局</el-button>
      </el-empty>
    </div>

    <!-- 带布局的主内容 -->
    <div v-else-if="currentLayout.id" class="layout-container" :class="{ 'has-add-panel': showAddPanel && isEditing }">
      <!-- 添加组件面板 -->
      <WidgetAddPanel
        v-if="showAddPanel && isEditing"
        class="add-panel"
        @add="addWidget"
        @showPresets="showPresetDialog = true"
      />

      <!-- 网格布局 -->
      <div class="layout-area fade-in-up">
        <div v-if="isEditing && layoutItems.length === 0" class="empty-layout-hint">
          <el-empty description="布局为空，点击「添加组件」开始配置" />
        </div>

        <ReportLayout
          v-model:layout-items="layoutItems"
          :is-editing="isEditing"
          :dashboard-data="dashboardData"
          @remove-widget="removeWidget"
          @edit-widget="editWidget"
        />
      </div>
    </div>

    <!-- 旧版兼容：无布局时使用旧版 widgets -->
    <div v-else-if="!loading && !error">
      <div class="dashboard-toolbar">
        <el-button :type="isEditing ? 'primary' : 'default'" @click="toggleEdit">
          {{ isEditing ? '完成编辑' : '自定义布局' }}
        </el-button>
        <el-button v-if="isEditing" type="success" @click="saveLegacyWidgets" :loading="savingLayout">
          保存布局
        </el-button>
        <el-button v-if="isEditing" @click="resetLegacyLayout">重置</el-button>
      </div>

      <div v-if="!isEditing" class="widget-grid">
        <div
          v-for="(w, idx) in visibleWidgets"
          :key="w.widget_type"
          class="widget-grid-item"
          :class="['widget-' + w.widget_type, 'fade-in-up']"
          :style="{ animationDelay: idx * 0.08 + 's' }"
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
              <div class="drag-handle"><el-icon><Sort /></el-icon></div>
              <div class="edit-item-preview">
                <DashboardWidget :widget="element" :dashboard-data="dashboardData" />
              </div>
              <el-tooltip :content="element.visible ? '点击隐藏' : '点击显示'" placement="top">
                <el-button
                  :icon="element.visible ? View : Hide"
                  :type="element.visible ? 'warning' : 'info'"
                  circle size="small"
                  @click="element.visible = !element.visible"
                />
              </el-tooltip>
            </div>
          </template>
        </draggable>

        <div v-if="hiddenWidgetTypes.length" class="add-widget-section">
          <el-divider />
          <h4>已隐藏的组件</h4>
          <div class="hidden-widgets">
            <el-tag v-for="w in hiddenWidgetTypes" :key="w.widget_type" closable @close="addLegacyWidget(w.widget_type)">
              {{ w.title }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 预设模板弹窗 -->
    <el-dialog v-model="showPresetDialog" title="预设布局模板" width="500px">
      <div class="preset-grid">
        <div
          v-for="preset in presets"
          :key="preset.key"
          class="preset-card"
          @click="applyPreset(preset.key)"
        >
          <div class="preset-icon">
            <el-icon :size="32"><component :is="preset.icon" /></el-icon>
          </div>
          <div class="preset-name">{{ preset.name }}</div>
          <div class="preset-desc">{{ preset.desc }}</div>
        </div>
      </div>
    </el-dialog>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="showRenameDialog" title="重命名布局" width="400px">
      <el-input v-model="renameValue" placeholder="布局名称" />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Sort, View, Hide, Plus, Edit, Delete, Setting } from "@element-plus/icons-vue"
import draggable from "vuedraggable"
import DashboardWidget from "@/components/DashboardWidget.vue"
import ReportLayout from "@/components/ReportLayout.vue"
import WidgetAddPanel from "@/components/WidgetAddPanel.vue"
import {
  getLayoutList, getLayoutDetail, createLayout, updateLayout, deleteLayout, saveWidgetBatch,
  getWidgetConfig, saveWidgetConfig, getDashboardData,
} from "@/api/dashboard"

const ALL_WIDGET_META = {
  data_source_count: { title: "数据源", defaultVisible: true },
  query_count:       { title: "查询次数", defaultVisible: true },
  export_count:      { title: "导出次数", defaultVisible: true },
  template_count:    { title: "模板数量", defaultVisible: true },
  recent_queries:    { title: "最近查询", defaultVisible: true },
  recent_templates:  { title: "最近模板", defaultVisible: true },
}

const presets = [
  { key: "default", name: "默认看板", desc: "4个统计卡 + 趋势和柱状图", icon: "Monitor" },
  { key: "analysis", name: "分析工作台", desc: "智能查询 + 图表 + 表格", icon: "DataAnalysis" },
  { key: "monitor", name: "大屏监控", desc: "紧凑统计卡 + 核心指标 + 趋势", icon: "Aim" },
  { key: "blank", name: "空白", desc: "从零开始自由搭建", icon: "Grid" },
]

export default {
  name: "Dashboard",
  components: {
    DashboardWidget, ReportLayout, WidgetAddPanel, draggable,
    Sort, View, Hide, Plus, Edit, Delete, Setting,
  },
  setup() {
    const loading = ref(true)
    const error = ref("")
    const isEditing = ref(false)
    const savingLayout = ref(false)

    // ===== 布局相关 =====
    const layouts = ref([])
    const currentLayoutId = ref(null)
    const currentLayout = ref({})
    const layoutItems = ref([])
    const showAddPanel = ref(false)
    const showPresetDialog = ref(false)
    const showRenameDialog = ref(false)
    const renameValue = ref("")

    // ===== 旧版兼容 =====
    const widgets = ref([])
    const dashboardData = ref({
      data_source_count: 0, query_count: 0, export_count: 0, template_count: 0,
      recent_queries: [], recent_templates: [],
    })
    const editingWidgets = ref([])

    const visibleWidgets = computed(() => widgets.value.filter(w => w.visible))

    const hiddenWidgetTypes = computed(() =>
      Object.entries(ALL_WIDGET_META)
        .filter(([type]) => !editingWidgets.value.some(w => w.widget_type === type))
        .map(([widget_type, meta]) => ({ widget_type, title: meta.title }))
    )

    // ===== 数据加载 =====
    const loadData = async () => {
      loading.value = true
      error.value = ""
      try {
        const [layoutList, widgetConfigs, data] = await Promise.all([
          getLayoutList().catch(() => []),
          getWidgetConfig(),
          getDashboardData(),
        ])
        layouts.value = layoutList
        widgets.value = widgetConfigs
        dashboardData.value = data

        // 自动跳转第一个布局或默认布局
        if (layoutList.length > 0) {
          const defaultLayout = layoutList.find(l => l.is_default) || layoutList[0]
          currentLayoutId.value = defaultLayout.id
          await switchToLayout(defaultLayout.id)
        }
      } catch (err) {
        console.error("加载仪表盘失败:", err)
        error.value = "加载仪表盘数据失败"
      } finally {
        loading.value = false
      }
    }

    const switchToLayout = async (id) => {
      try {
        const detail = await getLayoutDetail(id)
        currentLayout.value = detail
        layoutItems.value = detail.widgets.map(w => ({
          i: `w_${w.id}_${w.widget_type}_${Date.now()}`,
          x: w.grid_x, y: w.grid_y, w: w.grid_w, h: w.grid_h,
          widget_type: w.widget_type, widget_subtype: w.widget_subtype || "",
          title: w.title, extra_config: w.extra_config || {},
        }))
      } catch (err) {
        console.error("加载布局详情失败:", err)
        ElMessage.error("加载布局失败")
      }
    }

    const switchLayout = async (id) => {
      currentLayoutId.value = id
      await switchToLayout(id)
    }

    const createNewLayout = async () => {
      try {
        const layout = await createLayout({ name: "新建布局" })
        layouts.value.push(layout)
        currentLayoutId.value = layout.id
        currentLayout.value = { ...layout }
        layoutItems.value = []
        isEditing.value = true
        showAddPanel.value = true
        ElMessage.success("布局已创建")
      } catch (err) {
        ElMessage.error("创建布局失败")
      }
    }

    // ===== 编辑操作 =====
    const toggleEdit = () => {
      isEditing.value = !isEditing.value
      if (!isEditing.value) {
        showAddPanel.value = false
      }
    }

    const saveLayout = async () => {
      if (!currentLayoutId.value) return
      savingLayout.value = true
      try {
        const widgetsToSave = layoutItems.value.map(item => ({
          widget_type: item.widget_type,
          widget_subtype: item.widget_subtype || null,
          title: item.title,
          grid_x: item.x, grid_y: item.y, grid_w: item.w, grid_h: item.h,
          visible: item.visible !== false,
          extra_config: item.extra_config || {},
        }))
        const saved = await saveWidgetBatch(currentLayoutId.value, widgetsToSave)
        layoutItems.value = saved.map(w => ({
          i: `w_${w.id}_${w.widget_type}_${Date.now()}`,
          x: w.grid_x, y: w.grid_y, w: w.grid_w, h: w.grid_h,
          widget_type: w.widget_type, widget_subtype: w.widget_subtype || "",
          title: w.title, extra_config: w.extra_config || {},
        }))
        isEditing.value = false
        showAddPanel.value = false
        ElMessage.success("布局已保存")
      } catch (err) {
        console.error("保存布局失败:", err)
        ElMessage.error("保存布局失败")
      } finally {
        savingLayout.value = false
      }
    }

    const addWidget = (item) => {
      const newWidget = {
        i: `new_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        x: 0, y: 0,
        w: item.defaultW || 4,
        h: item.defaultH || 2,
        widget_type: item.type,
        widget_subtype: item.subtype || "",
        title: item.label,
        extra_config: {},
      }
      layoutItems.value.push(newWidget)
    }

    const removeWidget = (item) => {
      const idx = layoutItems.value.findIndex(w => w.i === item.i)
      if (idx >= 0) {
        layoutItems.value.splice(idx, 1)
      }
    }

    const editWidget = (item) => {
      ElMessage.info(`编辑 ${item.title} — 功能待扩展`)
    }

    const applyPreset = (key) => {
      const presetsMap = {
        default: [
          { type: "stat", subtype: "data_source_count", label: "数据源", w: 3, h: 1 },
          { type: "stat", subtype: "query_count", label: "查询次数", w: 3, h: 1 },
          { type: "stat", subtype: "export_count", label: "导出次��", w: 3, h: 1 },
          { type: "stat", subtype: "template_count", label: "模板数量", w: 3, h: 1 },
          { type: "chart", subtype: "line", label: "趋势图", w: 6, h: 4 },
          { type: "chart", subtype: "bar", label: "柱状图", w: 6, h: 4 },
        ],
        analysis: [
          { type: "nl2sql", label: "智能查询", w: 4, h: 6 },
          { type: "chart", subtype: "bar", label: "图表分析", w: 4, h: 3 },
          { type: "chart", subtype: "pie", label: "占比分析", w: 4, h: 3 },
          { type: "table", label: "数据表格", w: 8, h: 3 },
        ],
        monitor: [
          { type: "stat", subtype: "data_source_count", label: "数据源", w: 2, h: 1 },
          { type: "stat", subtype: "query_count", label: "查询次数", w: 2, h: 1 },
          { type: "stat", subtype: "export_count", label: "导出次数", w: 2, h: 1 },
          { type: "stat", subtype: "template_count", label: "模板数量", w: 2, h: 1 },
          { type: "chart", subtype: "gauge", label: "核心指标", w: 4, h: 2 },
          { type: "chart", subtype: "line", label: "实时趋势", w: 12, h: 3 },
        ],
        blank: [],
      }
      const presetItems = presetsMap[key] || presetsMap.default
      let iCounter = 0
      layoutItems.value = presetItems.map((item, idx) => ({
        i: `preset_${idx}_${Date.now()}`,
        x: 0, y: idx,
        w: item.w || 4, h: item.h || 2,
        widget_type: item.type,
        widget_subtype: item.subtype || "",
        title: item.label,
        extra_config: {},
      }))
      showPresetDialog.value = false
    }

    const renameLayout = async () => {
      renameValue.value = currentLayout.value.name || ""
      showRenameDialog.value = true
    }

    const confirmRename = async () => {
      if (!renameValue.value.trim()) return
      try {
        const updated = await updateLayout(currentLayoutId.value, { name: renameValue.value.trim() })
        currentLayout.value.name = updated.name
        const l = layouts.value.find(l => l.id === currentLayoutId.value)
        if (l) l.name = updated.name
        ElMessage.success("已重命名")
      } catch {
        ElMessage.error("重命名失败")
      }
      showRenameDialog.value = false
    }

    const handleDeleteLayout = async () => {
      try {
        await ElMessageBox.confirm(`确定删除布局「${currentLayout.value.name}」？`, "确认删除", {
          confirmButtonText: "确定删除", cancelButtonText: "取消", type: "warning",
        })
        await deleteLayout(currentLayoutId.value)
        layouts.value = layouts.value.filter(l => l.id !== currentLayoutId.value)
        if (layouts.value.length > 0) {
          currentLayoutId.value = layouts.value[0].id
          await switchToLayout(layouts.value[0].id)
        } else {
          currentLayout.value = {}
          layoutItems.value = []
          currentLayoutId.value = null
        }
        ElMessage.success("布局已删除")
      } catch { /* cancelled */ }
    }

    // ===== 旧版兼容操作 =====
    const toggleVisibility = (index) => {
      editingWidgets.value[index].visible = !editingWidgets.value[index].visible
    }

    const addLegacyWidget = (widgetType) => {
      const meta = ALL_WIDGET_META[widgetType]
      editingWidgets.value.push({
        widget_type: widgetType, title: meta.title, position: editingWidgets.value.length, visible: true,
      })
    }

    const saveLegacyWidgets = async () => {
      savingLayout.value = true
      try {
        const payload = { widgets: editingWidgets.value.map((w, i) => ({ widget_type: w.widget_type, title: w.title, visible: w.visible })) }
        const saved = await saveWidgetConfig(payload)
        widgets.value = saved
        isEditing.value = false
        ElMessage.success("布局已保存")
      } catch {
        ElMessage.error("保存布局失败")
      } finally {
        savingLayout.value = false
      }
    }

    const resetLegacyLayout = () => {
      ElMessageBox.confirm("重置将恢复默认布局，确定吗？", "确认", {
        confirmButtonText: "确定", cancelButtonText: "取消", type: "warning",
      }).then(() => {
        editingWidgets.value = Object.entries(ALL_WIDGET_META).map(([widget_type, meta], i) => ({
          widget_type, title: meta.title, position: i, visible: meta.defaultVisible,
        }))
        ElMessage.info('已恢复默认布局，点击"保存布局"生效')
      }).catch(() => {})
    }

    onMounted(() => {
      loadData()
    })

    return {
      loading, error, isEditing, savingLayout,
      layouts, currentLayoutId, currentLayout, layoutItems,
      showAddPanel, showPresetDialog, showRenameDialog, renameValue,
      presets,
      widgets, dashboardData, editingWidgets,
      visibleWidgets, hiddenWidgetTypes,
      switchLayout, createNewLayout, toggleEdit, saveLayout,
      addWidget, removeWidget, editWidget,
      applyPreset, renameLayout, confirmRename, handleDeleteLayout,
      toggleVisibility, addLegacyWidget,
      saveLegacyWidgets, resetLegacyLayout,
      Sort, View, Hide,
    }
  },
}
</script>

<style scoped>
.dashboard-content {
  padding: 20px;
}

/* 入场动画 */
.fade-in-up {
  animation: fadeInUp 0.5s ease forwards;
  opacity: 0;
}
.dashboard-toolbar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
}
.loading-container {
  padding: 40px;
}
.empty-state {
  margin-top: 60px;
}
.layout-container {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.layout-container.has-add-panel .layout-area {
  flex: 1;
  min-width: 0;
}
.add-panel {
  width: 240px;
  flex-shrink: 0;
  position: sticky;
  top: 20px;
}
.layout-area {
  flex: 1;
  min-width: 0;
}
.empty-layout-hint {
  padding: 60px 0;
}

/* 旧版兼容样式 */
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
  .widget-grid-item.widget-template_count { width: calc(50% - 10px); }
  .widget-grid-item.widget-recent_queries,
  .widget-grid-item.widget-recent_templates { width: 100%; }
}
@media (max-width: 500px) {
  .widget-grid-item.widget-data_source_count,
  .widget-grid-item.widget-query_count,
  .widget-grid-item.widget-export_count,
  .widget-grid-item.widget-template_count { width: 100%; }
}
.edit-mode { max-width: 800px; }
.edit-hint { color: #999; font-size: 13px; margin-bottom: 16px; }
.edit-item {
  display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
  padding: 8px; border: 1px solid #ebeef5; border-radius: 6px; background: #fff;
  transition: box-shadow 0.2s;
}
.edit-item:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.drag-handle { cursor: grab; color: #999; display: flex; align-items: center; flex-shrink: 0; }
.drag-handle:active { cursor: grabbing; }
.edit-item-preview { flex: 1; min-width: 0; pointer-events: none; }
.ghost { opacity: 0.4; border: 2px dashed #409eff; }
.add-widget-section { margin-top: 20px; }
.hidden-widgets { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }

/* 预设模板 */
.preset-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.preset-card {
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.preset-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64,158,255,0.15);
}
.preset-icon { color: #409eff; margin-bottom: 8px; }
.preset-name { font-weight: 600; margin-bottom: 4px; }
.preset-desc { font-size: 12px; color: #909399; }

/* 入场动画关键帧 */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
