# 仪表盘组件编辑功能设计方案

## 概述

扩展仪表盘布局模式下组件的编辑功能，将当前"功能待扩展"空壳实现为完整的编辑对话框体系。

## 交互流程

1. 编辑模式下，用户点击 WidgetSlot 头上的"编辑配置"按钮
2. 弹出 `WidgetEditorDialog`，根据组件类型（widget_type）动态渲染不同的编辑表单
3. 用户修改配置项后点击"保存"
4. 前端调用 `PUT /api/dashboard/layouts/{layoutId}/widgets/{widgetId}` 更新后端
5. 成功后关闭 Dialog，刷新布局数据

## 组件结构

```
frontend/src/components/
├── WidgetEditorDialog.vue      # 主对话框容器（新创建）
├── editors/
│   ├── StatEditor.vue          # 统计卡片编辑表单
│   ├── ChartEditor.vue         # 图表编辑表单
│   ├── TableEditor.vue         # 数据表格编辑表单
│   ├── Nl2sqlEditor.vue        # 智能查询编辑表单
│   └── IframeEditor.vue        # 外部嵌入编辑表单
```

## 各类型可编辑字段

### stat（统计卡片）
- `title`: 显示标题
- `widget_subtype`: 数据绑定（data_source_count / query_count / export_count / template_count）
- 保存至: title, widget_subtype

### chart（图表）
- `title`: 显示标题
- `widget_subtype`: 图表类型（line / bar / pie / scatter / radar / gauge）
- `extra_config.chartTitle`: 图表内部标题
- 保存至: title, widget_subtype, extra_config

### table（数据表格）
- `title`: 显示标题
- `extra_config.querySql`: 查询 SQL（未来版本对接数据源）
- 保存至: title, extra_config

### nl2sql（智能查询）
- `title`: 显示标题
- 保存至: title

### iframe（外部嵌入）
- `title`: 显示标题
- `extra_config.url`: 嵌入 URL
- 保存至: title, extra_config

## 数据流

```
WidgetSlot @edit → Dashboard.vue editWidget()
  → 打开 WidgetEditorDialog，传入 widget 对象
  → 用户编辑 → 确认保存
  → Dashboard.vue 调用 updateWidget(layoutId, widgetId, data)
  → 后端 DashboardService.update_widget() 保存到 extra_config
  → 刷新当前 widget 数据
```

## 涉及的修改文件

1. **新建** `frontend/src/components/WidgetEditorDialog.vue`
2. **新建** `frontend/src/components/editors/StatEditor.vue`
3. **新建** `frontend/src/components/editors/ChartEditor.vue`
4. **新建** `frontend/src/components/editors/TableEditor.vue`
5. **新建** `frontend/src/components/editors/Nl2sqlEditor.vue`
6. **新建** `frontend/src/components/editors/IframeEditor.vue`
7. **修改** `frontend/src/views/Dashboard.vue` — 实现 `editWidget` 方法
8. **修改** `frontend/src/components/WidgetSlot.vue` — 清理编辑入口（已就绪）
