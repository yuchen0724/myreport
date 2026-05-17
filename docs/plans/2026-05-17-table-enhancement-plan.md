# Phase 1A — 表格增强 实现计划

> **创建日期：** 2026-05-17
> **源文档：** `docs/frontend-enhancement-plan.md`
> **当前分支：** master（在开发完成后创建临时分支或直接在 master 上增量提交）

---

## Goal

在不推翻现有架构的前提下，对 `ReportView.vue` 和 `QueryResult.vue` 的表格交互做系统性增强，使报表用户从"看数据"升级到"配置数据"。

## Architecture

后端零改动，所有增强依赖 `el-table` 原生能力 + `sortablejs` localStorage 持久化。新增 `TableToolbar.vue` 组件和 `useTableStorage.js` composable，在 `ReportView.vue` 和 `QueryResult.vue` 中复用。

## Tech Stack

- Vue 3 (Composition API) + Element Plus
- sortablejs (列拖拽)
- localStorage（列顺序/宽/固定/汇总持久化）

---

### Task 1: 安装 sortablejs 依赖

**Objective:** 安装列拖拽排序所需的 npm 包

**Step 1:** 安装

```bash
cd /home/zhou/myreport/frontend
npm install sortablejs
npm install -D @types/sortablejs
```

**Step 2:** 验证

```bash
grep -n "sortable" package.json
# 应看到 "sortablejs": "^..."
```

**Step 3:** Commit

```bash
cd /home/zhou/myreport
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: 添加 sortablejs 依赖用于列拖拽排序"
```

---

### Task 2: 创建 useTableStorage composable

**Objective:** 创建 `frontend/src/composables/useTableStorage.js`，提供列顺序/列宽/固定列/汇总配置的 localStorage 读写

**Files:**
- Create: `frontend/src/composables/useTableStorage.js`

**Step 1:** 创建 composable

```js
// frontend/src/composables/useTableStorage.js
// 通用表格配置持久化 composable
// 使用 localStorage 存储，key 格式为 `table_config:${tableId}`

const STORAGE_PREFIX = 'table_config'

export function useTableStorage(tableId) {
  const storageKey = `${STORAGE_PREFIX}:${tableId}`

  function getConfig() {
    try {
      const raw = localStorage.getItem(storageKey)
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  }

  function saveConfig(config) {
    try {
      const existing = getConfig()
      const merged = { ...existing, ...config }
      localStorage.setItem(storageKey, JSON.stringify(merged))
    } catch (e) {
      console.warn('useTableStorage: 保存配置失败', e)
    }
  }

  // 列顺序
  function saveColumnOrder(keys) {
    saveConfig({ columnOrder: keys })
  }
  function loadColumnOrder() {
    return getConfig().columnOrder || null
  }

  // 列宽：{ [columnKey]: width }
  function saveColumnWidth(key, width) {
    const existing = getConfig()
    const columnWidths = existing.columnWidths || {}
    columnWidths[key] = width
    saveConfig({ columnWidths })
  }
  function loadColumnWidth(key) {
    const config = getConfig()
    return config.columnWidths?.[key] || null
  }

  // 固定列：{ [columnKey]: 'left'|'right'|false }
  function saveFixedColumn(key, direction) {
    const existing = getConfig()
    const fixedColumns = existing.fixedColumns || {}
    if (direction) {
      fixedColumns[key] = direction
    } else {
      delete fixedColumns[key]
    }
    saveConfig({ fixedColumns })
  }
  function loadFixedColumn(key) {
    const config = getConfig()
    return config.fixedColumns?.[key] || false
  }

  // 汇总配置：{ [columnKey]: { type: 'sum'|'avg'|'min'|'max'|'count' } }
  function saveSummaryConfig(cols) {
    saveConfig({ summaryColumns: cols })
  }
  function loadSummaryConfig() {
    return getConfig().summaryColumns || null
  }

  // 清除该 tableId 的所有配置
  function clearAll() {
    localStorage.removeItem(storageKey)
  }

  return {
    saveColumnOrder,
    loadColumnOrder,
    saveColumnWidth,
    loadColumnWidth,
    saveFixedColumn,
    loadFixedColumn,
    saveSummaryConfig,
    loadSummaryConfig,
    clearAll,
  }
}
```

**Step 2:** 验证

```bash
node -e "
const { useTableStorage } = require('./src/composables/useTableStorage.js');
// 这只是文件存在性检查；实际 localStorage 在 node 环境不可用
console.log('useTableStorage 导出可用');
" 2>&1 || echo "Node 环境无 localStorage，忽略"
```

**Step 3:** Commit

```bash
git add frontend/src/composables/useTableStorage.js
git commit -m "feat: 创建 useTableStorage composable，支持列顺序/列宽/固定列/汇总的 localStorage 持久化"
```

---

### Task 3: 创建 TableToolbar 组件

**Objective:** 创建 `frontend/src/components/TableToolbar.vue`，封装列显隐/搜索/拖拽柄/固定列/汇总行/行展开的 UI 和逻辑

**Files:**
- Create: `frontend/src/components/TableToolbar.vue`

**Step 1:** 创建组件

```vue
<template>
  <div class="table-toolbar">
    <!-- 列显隐控制 -->
    <el-popover placement="bottom-start" :width="220" trigger="click">
      <template #reference>
        <el-button size="small">
          <el-icon><Grid /></el-icon>
          列展示
        </el-button>
      </template>
      <div class="column-visibility">
        <el-checkbox
          v-model="checkAll"
          :indeterminate="isIndeterminate"
          @change="handleCheckAll"
        >
          全选
        </el-checkbox>
        <el-checkbox-group v-model="internalVisible" @change="handleCheckChange">
          <el-checkbox
            v-for="col in allColumns"
            :key="col.key || col"
            :label="col.key || col"
            :value="col.key || col"
          >
            {{ col.label || col }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
    </el-popover>

    <!-- 搜索框 -->
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

    <!-- 行展开切换 -->
    <el-button
      v-if="enableExpand"
      size="small"
      :type="expanded ? 'primary' : 'default'"
      @click="$emit('toggle-expand')"
      style="margin-left: 10px"
    >
      <el-icon><Rank /></el-icon>
      行展开
    </el-button>

    <slot />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Grid, Search, Rank } from '@element-plus/icons-vue'

const props = defineProps({
  allColumns: { type: Array, required: true },       // [{ key, label }] 或字符串数组
  modelValue: { type: Array, required: true },        // v-model: 当前可见列
  enableExpand: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'update:searchText', 'toggle-expand'])

const searchText = ref('')
watch(searchText, (val) => emit('update:searchText', val))

const internalVisible = ref([...props.modelValue])
watch(() => props.modelValue, (val) => {
  internalVisible.value = [...val]
})

const checkAll = computed(() => internalVisible.value.length === props.allColumns.length)
const isIndeterminate = computed(() => {
  const len = internalVisible.value.length
  return len > 0 && len < props.allColumns.length
})

function handleCheckAll(val) {
  const all = props.allColumns.map(c => c.key || c)
  emit('update:modelValue', val ? all : [])
}

function handleCheckChange(value) {
  emit('update:modelValue', [...value])
}
</script>

<style scoped>
.table-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.column-visibility {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
```

**Step 2:** 验证

```bash
# 组件语法检查（无 runtime，走 Vite 编译）
cd /home/zhou/myreport/frontend
npx vue-tsc --noEmit src/components/TableToolbar.vue 2>&1 || echo "可直接用 vite 验证"
```

**Step 3:** Commit

```bash
git add frontend/src/components/TableToolbar.vue
git commit -m "feat: 创建 TableToolbar 通用表格工具栏组件"
```

---

### Task 4: 增强 ReportView.vue — 列拖拽排序

**Objective:** 在 ReportView.vue 的 el-table 上挂载 SortableJS 实现列拖拽排序

**Files:**
- Modify: `frontend/src/views/ReportView.vue`

**Step 1:** 在 script setup 中添加 import 和拖拽逻辑（在 `handleSortChange` 之后添加）

在 `<script setup>` 中修改/添加以下内容：

```js
// 在 import 区域添加
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
// 新增
import Sortable from 'sortablejs'
import { useTableStorage } from '@/composables/useTableStorage'

// 在 ref 声明区域添加
// 表格引用（给拖拽使用）
const tableRef = ref(null)

// useTableStorage — 用经度路径做 tableId（避免不同菜单冲突）
const route = useRoute()
const tableId = computed(() => `report:${route.params.id || 'default'}`)
const storage = useTableStorage(tableId.value)

// 在 loadData 成功后，恢复 localStorage 中的列顺序
const loadData = async () => {
  // ... 现有代码不变 ...
  // 在 columns.value = cols 赋值后添加列顺序恢复逻辑
  // 找到 data.value 赋值后的位置添加：
  columns.value = cols
  // 恢复持久化的列顺序
  const savedOrder = storage.loadColumnOrder()
  if (savedOrder && savedOrder.length > 0) {
    // 仅保留当前数据中存在的列
    const validOrder = savedOrder.filter(c => cols.includes(c))
    if (validOrder.length > 0) {
      columns.value = validOrder
    }
  }
  // ... 后续代码 ...
}
```

**Step 2:** 在模板中的 `el-table` 上添加 `ref="tableRef"`，并在 `onMounted`/`watch` 数据变化后初始化 Sortable

在 el-table 上：
```html
<el-table
  ref="tableRef"
  ...
>
```

在 loadData 成功后初始化拖拽：
```js
// 在 loadData 的 data.value 赋值后（columns.value 之后），添加：
nextTick(() => {
  initColumnDrag()
})

// 新增函数
function initColumnDrag() {
  if (!tableRef.value) return
  const headerRow = tableRef.value.$el.querySelector('.el-table__header-wrapper .el-table__header th')
  if (!headerRow || headerRow._sortableInitialized) return
  
  const el = tableRef.value.$el.querySelector('.el-table__header-wrapper .el-table__header tr')
  if (!el) return

  Sortable.create(el, {
    animation: 150,
    handle: '.el-table__column-header',  // 拖拽柄为整个表头单元格
    onEnd: (evt) => {
      const oldIndex = evt.oldIndex
      const newIndex = evt.newIndex
      if (oldIndex === newIndex) return

      // 更新 visibleColumns 数组顺序
      const newOrder = [...visibleColumns.value]
      const [moved] = newOrder.splice(oldIndex, 1)
      newOrder.splice(newIndex, 0, moved)
      visibleColumns.value = newOrder
      
      // 持久化列顺序
      storage.saveColumnOrder(newOrder)
    }
  })
  
  // 标记已初始化
  el._sortableInitialized = true
}
```

**Step 3:** 解决列拖拽与列排序冲突：为表头列添加统一的拖拽触发

在 `initColumnDrag` 中已用 `.el-table__column-header` 作为 handle。el-table 的排序可点击由 `<el-table-column sortable="custom">` 触发——两者在 `el-table-column` 的 header 上共存。

为了让拖拽不和排序冲突，使用表头单元格左侧 8px 的拖拽柄区域。简化方案：整个表头可拖拽，排序通过表头旁的排序按钮完成。

只需确保 `sortable="custom"` 仍在列上即可。用户先拖拽排序列顺序，再点击表头排序按钮（el-table 原生排序箭头的区域不在 Sortable handle 覆盖范围内）。

**Step 4:** Commit

```bash
git add frontend/src/views/ReportView.vue
git commit -m "feat(ReportView): 添加列拖拽排序功能及 SortableJS 集成"
```

---

### Task 5: 增强 ReportView.vue — 列宽拖动 + 持久化

**Objective:** 在 ReportView.vue 中监听 `@header-dragend` 事件持久化列宽，`onMounted` 时恢复

**Files:**
- Modify: `frontend/src/views/ReportView.vue`

**Step 1:** 在 el-table 上添加 `@header-dragend` 事件

```html
<el-table
  ref="tableRef"
  :data="data"
  border
  stripe
  :default-sort="{ prop: sortProp, order: sortOrder }"
  @sort-change="handleSortChange"
  @header-dragend="handleHeaderDragEnd"
  max-height="500"
  style="width: 100%"
>
```

**Step 2:** 添加 handler 和恢复逻辑

在 script ���添加：
```js
// 列宽拖动后持久化
function handleHeaderDragEnd(newWidth, oldWidth, column, event) {
  if (column && column.property) {
    storage.saveColumnWidth(column.property, newWidth)
  }
}
```

在模板中为每个 `el-table-column` 添加 `:width` 绑定：
```html
<el-table-column
  v-for="col in visibleColumns"
  :key="col"
  :prop="col"
  :label="col"
  :width="storage.loadColumnWidth(col) || undefined"
  min-width="80"
  show-overflow-tooltip
  sortable="custom"
/>
```

**Step 3:** Commit

```bash
git add frontend/src/views/ReportView.vue
git commit -m "feat(ReportView): 添加列宽拖动持久化功能"
```

---

### Task 6: 增强 ReportView.vue — 固定列

**Objective:** 表头列操作按钮支持"固定到左侧/右侧/取消固定"，配置持久化

**Files:**
- Modify: `frontend/src/views/ReportView.vue`

**Step 1:** 替换 `el-table-column` 的模板以支持固定列

```html
<el-table-column
  v-for="col in visibleColumns"
  :key="col"
  :prop="col"
  :label="col"
  :width="storage.loadColumnWidth(col) || undefined"
  :fixed="storage.loadFixedColumn(col) || false"
  min-width="80"
  show-overflow-tooltip
  sortable="custom"
>
  <!-- 列头操作按钮（固定列控制） -->
  <template #header="{ column }">
    <div class="column-header-with-actions">
      <span>{{ col }}</span>
      <el-dropdown trigger="click" size="small" @command="(cmd) => handleColumnAction(cmd, col)">
        <el-button size="small" circle :icon="MoreFilled" class="col-action-btn" />
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="fixed-left" :disabled="storage.loadFixedColumn(col) === 'left'">
              固定到左侧
            </el-dropdown-item>
            <el-dropdown-item command="fixed-right" :disabled="storage.loadFixedColumn(col) === 'right'">
              固定到右侧
            </el-dropdown-item>
            <el-dropdown-item command="clear-fixed" :disabled="!storage.loadFixedColumn(col)">
              取消固定
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </template>
</el-table-column>
```

**Step 2:** 添加 handler 函数

```js
import { MoreFilled } from '@element-plus/icons-vue'

function handleColumnAction(cmd, col) {
  switch (cmd) {
    case 'fixed-left':
      storage.saveFixedColumn(col, 'left')
      break
    case 'fixed-right':
      storage.saveFixedColumn(col, 'right')
      break
    case 'clear-fixed':
      storage.saveFixedColumn(col, false)
      break
  }
  // 强制重新渲染以反映固定列变化
  // 通过解构重构 visibleColumns 触发重新渲染
  visibleColumns.value = [...visibleColumns.value]
}
```

**Step 3:** 添加样式

```css
.column-header-with-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.col-action-btn {
  opacity: 0.4;
  transition: opacity 0.2s;
}
.col-action-btn:hover {
  opacity: 1;
}
```

**Step 4:** Commit

```bash
git add frontend/src/views/ReportView.vue
git commit -m "feat(ReportView): 添加列固定功能（左侧/右侧/取消），配置持久化"
```

---

### Task 7: 增强 ReportView.vue — 汇总行

**Objective:** 在 el-table 上启用 `show-summary` + `summary-method`，表头下拉菜单选择汇总类型

**Files:**
- Modify: `frontend/src/views/ReportView.vue`

**Step 1:** 在 el-table 上添加汇总相关属性

```html
<el-table
  ref="tableRef"
  :data="data"
  border
  stripe
  :default-sort="{ prop: sortProp, order: sortOrder }"
  @sort-change="handleSortChange"
  @header-dragend="handleHeaderDragEnd"
  :show-summary="true"
  :summary-method="handleSummary"
  max-height="500"
  style="width: 100%"
>
```

**Step 2:** 在 el-table-column 的列头操作下拉中添加汇总选项

```diff
- <!-- 在列头模板的 el-dropdown-menu 中添加汇总选项 -->
+ <el-dropdown-item divided command="summary-sum">汇总：求和</el-dropdown-item>
+ <el-dropdown-item command="summary-avg">汇总：平均数</el-dropdown-item>
+ <el-dropdown-item command="summary-min">汇总：最小值</el-dropdown-item>
+ <el-dropdown-item command="summary-max">汇总：最大值</el-dropdown-item>
+ <el-dropdown-item command="summary-count">汇总：计数</el-dropdown-item>
+ <el-dropdown-item divided command="clear-summary">清除汇总</el-dropdown-item>
```

**Step 3:** 添加 handleSummary 和 handleColumnAction 中的汇总逻辑

```js
// 汇总函数
const summaryColumns = ref({}) // { colName: 'sum'|'avg'|'min'|'max'|'count' }

function handleSummary({ columns, data }) {
  const config = storage.loadSummaryConfig()
  if (!config || Object.keys(config).length === 0) return []

  return columns.map((column, index) => {
    const colKey = column.property
    const summary = config[colKey]
    if (!summary) return ''

    const values = data.map(row => Number(row[colKey])).filter(v => !isNaN(v))
    if (values.length === 0) return ''

    let result
    switch (summary) {
      case 'sum': result = values.reduce((a, b) => a + b, 0); break
      case 'avg': result = values.reduce((a, b) => a + b, 0) / values.length; break
      case 'min': result = Math.min(...values); break
      case 'max': result = Math.max(...values); break
      case 'count': result = values.length; break
      default: return ''
    }

    const label = { sum: '合计', avg: '平均', min: '最小', max: '最大', count: '计数' }
    return `${label[summary]}: ${typeof result === 'number' ? result.toFixed(2) : result}`
  })
}

// 在 handleColumnAction 中扩展
function handleColumnAction(cmd, col) {
  // ... 现有固定列逻辑 ...
  
  // 汇总命令
  if (cmd.startsWith('summary-')) {
    const type = cmd.replace('summary-', '')
    let summaryConfig = storage.loadSummaryConfig() || {}
    summaryConfig = { ...summaryConfig, [col]: type }
    storage.saveSummaryConfig(summaryConfig)
    // 触发汇总重新计算
    visibleColumns.value = [...visibleColumns.value]
    return
  }
  if (cmd === 'clear-summary') {
    const summaryConfig = storage.loadSummaryConfig() || {}
    if (summaryConfig[col]) {
      delete summaryConfig[col]
      storage.saveSummaryConfig(summaryConfig)
      visibleColumns.value = [...visibleColumns.value]
    }
    return
  }
  
  // ... 现有固定列逻辑 ...
}
```

注意：需要重构 `handleColumnAction` 使其能正确处理多个命令类型。建议使用一个 switch 结构：

```js
function handleColumnAction(cmd, col) {
  switch (true) {
    case cmd === 'fixed-left':
      storage.saveFixedColumn(col, 'left')
      break
    case cmd === 'fixed-right':
      storage.saveFixedColumn(col, 'right')
      break
    case cmd === 'clear-fixed':
      storage.saveFixedColumn(col, false)
      break
    case cmd.startsWith('summary-'):
      const type = cmd.replace('summary-', '')
      const sc = storage.loadSummaryConfig() || {}
      storage.saveSummaryConfig({ ...sc, [col]: type })
      break
    case cmd === 'clear-summary':
      const sc2 = storage.loadSummaryConfig() || {}
      if (sc2[col]) {
        delete sc2[col]
        storage.saveSummaryConfig(sc2)
      }
      break
  }
  // 强制刷新
  visibleColumns.value = [...visibleColumns.value]
}
```

**Step 4:** Commit

```bash
git add frontend/src/views/ReportView.vue
git commit -m "feat(ReportView): 添加汇总行功能（求和/均值/最小/最大/计数），列头下拉配置"
```

---

### Task 8: 增强 ReportView.vue — 行展开子表

**Objective:** 为 el-table 添加 `type="expand"` 列，展开后显示该行的所有字段

**Files:**
- Modify: `frontend/src/views/ReportView.vue`

**Step 1:** 在 el-table 中的第一个子元素位置添加展开列

```html
<el-table-column type="expand" v-if="showExpand">
  <template #default="{ row }">
    <div class="expand-detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item
          v-for="(val, key) in row"
          :key="key"
          :label="key"
        >
          {{ val !== null && val !== undefined ? val : '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </template>
</el-table-column>
```

**Step 2:** 添加状态和切换方法

```js
const showExpand = ref(false)

// 从上一任务中继承的 TableToolbar 通过 $emit('toggle-expand') 触��
function toggleExpand() {
  showExpand.value = !showExpand.value
}
```

**Step 3:** 在 TableToolbar 的 `@toggle-expand` 事件上绑定

```html
<TableToolbar
  ...
  @toggle-expand="toggleExpand"
/>
```

（此处假设 ReportView.vue 已使用 TableToolbar 组件。——该组件替换现有的列展示按钮和搜索框，在任务 10 中完成替换）

**Step 4:** 添加样式

```css
.expand-detail {
  padding: 12px;
}
```

**Step 5:** Commit

```bash
git add frontend/src/views/ReportView.vue
git commit -m "feat(ReportView): 添加行展开子表功能"
```

---

### Task 9: 增强 ReportView.vue — 集成 TableToolbar 组件

**Objective:** 把内联的列展示 + 搜索框替换为 Task 3 创建的 TableToolbar 组件

**Files:**
- Modify: `frontend/src/views/ReportView.vue`

**Step 1:** 导入并注册 TableToolbar 组件

```js
import TableToolbar from '@/components/TableToolbar.vue'
```

**Step 2:** 替换现有的 `<div class="table-toolbar">...</div>` 为：

```html
<TableToolbar
  v-if="data.length > 0"
  :all-columns="columns"
  v-model="visibleColumns"
  v-model:search-text="searchText"
  :enable-expand="columns.length > 6"
  :expanded="showExpand"
  @toggle-expand="toggleExpand"
/>
```

注意：Enable expand 的条件设为列数 > 6，因为列少时展开没有意义。

**Step 3:** 删除旧的内联列展示和搜索框代码

删除原来的：
```html
<div class="table-toolbar">
  <el-popover ...>...</el-popover>
  <el-input ...>...</el-input>
</div>
```

**Step 4:** 安装 element-plus icons（如果尚未全量引入）

检查 `frontend/src/main.js` 中是否已有 `import * as ElementPlusIconsVue`。如果没有，添加：
```js
// 在 main.js 中
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
```

**Step 5:** 重新验证编译

```bash
cd /home/zhou/myreport/frontend
npx vite build 2>&1 | tail -10
# 期望: ✓ built in X.XXs
```

**Step 6:** Commit

```bash
git add frontend/src/views/ReportView.vue
git commit -m "refactor(ReportView): 集成 TableToolbar 组件替代内联列展示与搜索"
```

---

### Task 10: 集成到 QueryResult.vue

**Objective:** 对 `QueryResult.vue` 应用相同的列拖拽/列宽/固定列/汇总行/行展开增强

**Files:**
- Modify: `frontend/src/views/QueryResult.vue`

**Step 1:** 检测 `QueryResult.vue` 的当前行数据格式

当前 `QueryResult.vue` 的 `result.columns` 是字符串数组，`result.rows` 是用数字索引的数组对象（`{ 0: val1, 1: val2 }`），不支持列顺序持久化。

把 `QueryResult` 从 Options API 改为 Composition API（`<script setup>`），统一数据格式为 `{ col1: val1, col2: val2 }` 的结构。

**具体改动：**

1. 通过 `handlePageChange` emit 的 `re-query` 由父组件处理数据获取
2. 添加 `useTableStorage` composable
3. 添加列拖拽、列宽、固定列、汇总、行展开支持

> **注意：** `QueryResult.vue` 是一个只有 184 行的组件，改动量可控。但更重要的是，该组件的数据来自父组件 props（`dataSourceId`, `querySql`），通过 emit 触发父组件重新请求。这是正确的职责分离。

**简化方案：** QueryResult.vue 在当前项目中的使用场景是 NL2SQLEditor 的结果面板和 QueryEditor 的结果面板。它接收的 `result.columns` 是字符串数组、`result.rows` 是数字索引数组。

对 QueryResult.vue 的最小改动：

1. 在 el-table 模板中添加 `@header-dragend`, `show-summary`, `summary-method`, 和展开列
2. 复用 useTableStorage（tableId = `query:${props.dataSourceId}`）

具体改动：
```js
// 在 setup() 中添加
import { useTableStorage } from '@/composables/useTableStorage'

const tableId = computed(() => `query:${props.dataSourceId || 'default'}`)
const storage = useTableStorage(tableId.value)

// 转换为对象数组供 el-table 使用
const tableData = computed(() => {
  return result.value.rows.map(row => {
    const obj = {}
    result.value.columns.forEach((col, i) => { obj[col] = row[i] })
    return obj
  })
})

const visibleColumns = ref(result.value.columns)
watch(() => result.value.columns, (cols) => {
  visibleColumns.value = [...cols]
  const savedOrder = storage.loadColumnOrder()
  if (savedOrder && savedOrder.length > 0) {
    const valid = savedOrder.filter(c => cols.includes(c))
    if (valid.length > 0) visibleColumns.value = valid
  }
})

// 汇总
function handleSummary({ columns, data }) {
  const config = storage.loadSummaryConfig()
  if (!config) return []
  return columns.map(col => {
    const summary = config[col.property]
    if (!summary) return ''
    const vals = data.map(r => Number(r[col.property])).filter(v => !isNaN(v))
    if (vals.length === 0) return ''
    let result
    switch (summary) {
      case 'sum': result = vals.reduce((a,b) => a+b, 0); break
      case 'avg': result = vals.reduce((a,b) => a+b, 0) / vals.length; break
      case 'min': result = Math.min(...vals); break
      case 'max': result = Math.max(...vals); break
      case 'count': result = vals.length; break
    }
    const label = { sum: '合计', avg: '平均', min: '最小', max: '最大', count: '计数' }
    return `${label[summary]}: ${result.toFixed(2)}`
  })
}
```

模板改为引用 `tableData` 而非 `result.rows`：
```html
<el-table :data="tableData" v-loading="loading" @header-dragend="handleHeaderDragEnd" :show-summary="true" :summary-method="handleSummary">
  <el-table-column type="expand" v-if="showExpand">
    <template #default="{ row }">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-for="(val, key) in row" :key="key" :label="key">{{ val ?? '-' }}</el-descriptions-item>
      </el-descriptions>
    </template>
  </el-table-column>
  <el-table-column
    v-for="(col, index) in visibleColumns"
    :key="index"
    :prop="col"
    :label="col"
    :width="storage.loadColumnWidth(col) || undefined"
    :fixed="storage.loadFixedColumn(col) || false"
    min-width="80"
    show-overflow-tooltip
  >
    <template #header>
      <div class="column-header-with-actions">
        <span>{{ col }}</span>
        <el-dropdown trigger="click" size="small" @command="(cmd) => handleColumnAction(cmd, col)">
          <el-button size="small" circle :icon="MoreFilled" class="col-action-btn" />
          <template #dropdown> ... </template>
        </el-dropdown>
      </div>
    </template>
  </el-table-column>
</el-table>
```

**Step 2:** Commit

```bash
git add frontend/src/views/QueryResult.vue
git commit -m "feat(QueryResult): 添加列拖拽/列宽/固定列/汇总/行展开功能"
```

---

### Task 11: 回归验证

**Objective:** 验证 Phase 1A 所有功能正确，无编译错误和运行时异常

**Step 1:** 前端构建

```bash
cd /home/zhou/myreport/frontend
npx vite build 2>&1
# 期望: ✓ built in X.XXs
```

**Step 2:** 手动验收清单

1. 进入报表页（如 `/report/1`）→ 数据加载后 → 拖拽某一列到第1列 → 刷新页面 → 该列仍在第1列
2. 拖动列头右侧边线加宽 → 刷新 → 列宽保持
3. 点击列头操作按钮 → "固定到左侧" → 滚动 → 该列不滚动
4. 点击列头操作按钮 → "汇总：求和" → 表尾显示合计值
5. 点击列头"→ "行展开"按钮 → 每一行出现展开箭头 → 点击展开 → 显示该行所有字段
6. 列显隐取消 "天数" → 表格中天数列消失 → 重新勾选 → 恢复

**Step 3:** Commit（最终汇总 commits）

无需额外提交（已在每个任务完成后提交）。

---
