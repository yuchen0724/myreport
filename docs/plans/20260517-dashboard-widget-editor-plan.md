# 仪表盘组件编辑功能 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 将仪表盘布局模式下组件编辑的"功能待扩展"空壳，实现为完整的编辑对话框体系，支持 5 种组件类型的属性编辑和实时保存。

**Architecture:** 
- 新建 `WidgetEditorDialog.vue` 作为通用编辑对话框容器，根据 `widget_type` 动态加载对应的 `editors/*Editor.vue` 子表单
- 每个子表单组件只负责自己类型的字段渲染和校验，通过 emit 把表单数据返回给 Dialog
- Dialog 组装 payload，emit `saved` 事件让父组件（Dashboard.vue）调用 API 保存
- 保存成功后父组件重新加载布局以刷新数据

**Tech Stack:** Vue 3 (Options API) + Element Plus + Axios

---

### Task 1: 创建 editors/ 子组件目录和 5 个 Editor 子表单

**Objective:** 创建 `frontend/src/components/editors/` 目录，实现各类型的编辑表单。

**Step 1: 创建目录**

```bash
mkdir -p /home/zhou/myreport/frontend/src/components/editors
```

**Step 2: 创建 StatEditor.vue**

`frontend/src/components/editors/StatEditor.vue`
- 编辑字段：title（组件标题）、widget_subtype（数据绑定：下拉选择 data_source_count / query_count / export_count / template_count）
- 用 `reactive` 初始化 form，从 props.widget 取当前值
- `watch` form 的变化，emit `update:modelValue` 给父组件

**Step 3: 创建 ChartEditor.vue**

`frontend/src/components/editors/ChartEditor.vue`
- 编辑字段：title（组件标题）、widget_subtype（图表类型：line/bar/pie/scatter/radar/gauge）、chartTitle（图表内部标题，来自 extra_config.chartTitle）

**Step 4: 创建 TableEditor.vue**

`frontend/src/components/editors/TableEditor.vue`
- 编辑字段：title（组件标题）、querySql（查询 SQL，来自 extra_config.querySql，textarea）

**Step 5: 创建 Nl2sqlEditor.vue**

`frontend/src/components/editors/Nl2sqlEditor.vue`
- 编辑字段：title（组件标题）

**Step 6: 创建 IframeEditor.vue**

`frontend/src/components/editors/IframeEditor.vue`
- 编辑字段：title（组件标题）、url（嵌入 URL，来自 extra_config.url）

---

### Task 2: 创建 WidgetEditorDialog.vue

**Objective:** 创建主编辑对话框组件

**Files:**
- Create: `frontend/src/components/WidgetEditorDialog.vue`

**关键设计：**
- `v-model` 控制显隐
- 通过 `:widget` prop 接收要编辑的组件对象
- 内部通过 `computed` 根据 `widget.widget_type` 映射到对应的 Editor 子组件
- 子组件通过 `v-model` 绑定 formData，Dialoag 维护一份 formData reactive 对象
- 点击"保存"时，Dialog 将 formData → 组装 `{ title, widget_subtype, extra_config }` payload → emit `saved` 事件
- "取消"或关闭 Dialog 时不做任何持久化

**保存逻辑细节：**
Dialog 的 `handleSave` 组装 payload：
```js
const payload = {
  title: formData.title,
  extra_config: { ...existingExtraConfig }
}
// 只覆盖 Editor 中编辑过的字段
if (formData.widget_subtype !== undefined) payload.widget_subtype = formData.widget_subtype
if (formData.url !== undefined) payload.extra_config.url = formData.url
if (formData.querySql !== undefined) payload.extra_config.querySql = formData.querySql
if (formData.chartTitle !== undefined) payload.extra_config.chartTitle = formData.chartTitle
// 保留 chartData/tableData 等由 dashboardData 注入的数据
if (props.widget.extra_config?.chartData) payload.extra_config.chartData = props.widget.extra_config.chartData
if (props.widget.extra_config?.tableData) payload.extra_config.tableData = props.widget.extra_config.tableData
```

emit 格式：`emit("saved", { widgetId, payload })`

其中 `widgetId` 从 `widget.i` 解析：`parseInt(widget.i?.split("_")[1], 10)`

---

### Task 3: 修改 Dashboard.vue — 集成编辑对话框

**Objective:** 将 editWidget 从空壳改为打开 Dialog，并实现保存后刷新

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

**需要做的修改：**

1. **添加 import**（在 `<script>` 开头已有 import 区域）
   - `import WidgetEditorDialog from "@/components/WidgetEditorDialog.vue"`（已有同类 import，紧随其后）
   - 在 `from "@/api/dashboard"` 的 import 中添加 `updateWidget`

2. **在 components 注册**（第 222-226 行）
   - 添加 `WidgetEditorDialog`

3. **在 setup 中添加状态变量**（与 `showAddPanel` 同区域）
   ```js
   const showWidgetEditor = ref(false)
   const editingWidgetRef = ref(null)
   ```

4. **替换 editWidget 函数**（第 435-437 行）
   ```js
   const editWidget = (item) => {
     editingWidgetRef.value = item
     showWidgetEditor.value = true
   }
   ```

5. **添加 handleWidgetSaved 函数**（在 saveLayout 附近）
   ```js
   const handleWidgetSaved = async ({ widgetId, payload }) => {
     if (!currentLayoutId.value || !widgetId) return
     savingLayout.value = true
     try {
       await updateWidget(currentLayoutId.value, widgetId, payload)
       ElMessage.success("组件已更新")
       await switchToLayout(currentLayoutId.value)
     } catch (err) {
       console.error("保存组件配置失败:", err)
       ElMessage.error("保存组件配置失败")
     } finally {
       savingLayout.value = false
     }
   }
   ```

6. **在模板中添加 Dialog**（在 `</template>` 闭合前，现有 Dialog 后面）
   ```html
   <WidgetEditorDialog
     v-model="showWidgetEditor"
     :widget="editingWidgetRef"
     @saved="handleWidgetSaved"
   />
   ```

7. **在 return 中添加新变量/函数**（第 566-579 行）
   - 添加 `showWidgetEditor`, `editingWidgetRef`, `handleWidgetSaved` 到 return 对象中
   - 将 `editWidget` 替换为新的引用

---

### Task 4: 验证前端构建

**Objective:** 确认所有新文件语法正确，前端构建通过

**Step 1: 构建验证**

```bash
cd /home/zhou/myreport/frontend
NODE_OPTIONS="--max-old-space-size=2048" npx vite build --ssr src/main.js
```

Expected: 看到 `X modules transformed` + 无错误退出（exit 0）

---

### 完整改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/components/editors/StatEditor.vue` | 新建 | ~35 行，stat 编辑表单 |
| `frontend/src/components/editors/ChartEditor.vue` | 新建 | ~45 行，chart 编辑表单 |
| `frontend/src/components/editors/TableEditor.vue` | 新建 | ~40 行，table 编辑表单 |
| `frontend/src/components/editors/Nl2sqlEditor.vue` | 新建 | ~30 行，nl2sql 编辑表单 |
| `frontend/src/components/editors/IframeEditor.vue` | 新建 | ~38 行，iframe 编辑表单 |
| `frontend/src/components/WidgetEditorDialog.vue` | 新建 | ~130 行，主编辑对话框 |
| `frontend/src/views/Dashboard.vue` | 修改 | ~10 行改动（import、components、setup、template、return）|

### 验证清单

- [ ] `npm run build / vite build --ssr` 通过
- [ ] 进入某个布局的编辑模式 → 点击组件上的编辑按钮 → Dialog 弹出且显示正确的编辑表单
- [ ] 编辑统计卡片标题 + 切换数据绑定 → 保存 → 卡片更新
- [ ] 编辑图表类型（bar → pie） → 保存 → 图表切换显示
- [ ] 编辑 iframe URL → 保存 → 嵌入页面更新
- [ ] 编辑 nl2sql 标题 → 保存 → 标题更新
- [ ] 修改后刷新页面 → 变更已持久化
