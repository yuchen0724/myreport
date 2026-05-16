# 前端增强开发计划 — 表格 + 图表 + 报表布局器

> **基线版本：** v1.0
> **创建日期：** 2026-05-16
> **适用项目：** custom-report-system (myreport)
> **前置文档：** `docs/development-roadmap.md`（本计划作为其第四阶段的补充细化）

---

## 一、背景与目标

当前系统已完成模板管理、NL2SQL、异步导出等核心功能，但在前端交互层面存在以下短板：

1. **表格交互弱** — el-table 仅支持列显隐和前端排序，无列拖拽排序、列宽持久化、固定列、汇总行
2. **图表能力受限于基础类型** — ChartRenderer 已注册 7 种 ECharts 类型，但数据视图、区域缩放、钻取、联动等高频交互缺失
3. **报表布局固化** — Dashboard 仅支持预定义 Widget 的排序和显隐，无法自由组合表格/图表/NL2SQL 面板

**目标**：在不推翻现有架构的前提下，对三者做系统性增强，使报表用户能从"看数据"升级到"配置数据"。

---

## 二、架构总览

```
Phase 1 (2.5周)                      Phase 2 (后续)
├─ 1A 表格增强 ◄── 现在从这里开始     ├─ 完整网格布局器 (grid-layout-plus)
├─ 1B 图表增强                       ├─ 更多图表类型 (heatmap/treemap/boxplot)
├─ 1C 报表布局器 (快速版)              ├─ 多级表头 (需后端配合)
└─ 回归验证                          └─ 布局模板分享
```

三段相对独立，可并行也可串行。推荐顺序：1A → 1B → 1C。

---

## 三、1A — 表格增强

### 3.1 影响范围

| 文件 | 当前行数 | 操作 | 说明 |
|------|---------|------|------|
| `frontend/src/views/ReportView.vue` | 547 | 修改 | 集成新增功能 |
| `frontend/src/views/QueryResult.vue` | 185 | 修改 | 集成新增功能 |
| `frontend/src/components/TableToolbar.vue` | — | **新建** | 通用表格工具栏组件 |
| `frontend/src/composables/useTableStorage.js` | — | **新建** | localStorage 序列化/恢复 Hook |

### 3.2 任务清单

| # | 任务 | 实现方式 | 后端影响 | 工时 |
|---|------|---------|---------|------|
| 1 | **列拖拽排序** | 在 `el-table` header-row 上挂载 `sortablejs` 实例，拖拽后更新 `visibleColumns` 数组顺序并写入 localStorage | 无 | 0.5d |
| 2 | **列宽拖动 + 持久化** | `el-table-column` 的 `resizable` 属性默认开启，`@header-dragend` 事件获取列宽，按 `tableId + columnKey` 写入 localStorage 并在 `onMounted` 时恢复 | 无 | 0.3d |
| 3 | **固定列** | 表头悬浮操作按钮，调用 `el-table-column` 的 `fixed` 属性，配置存入 localStorage | 无 | 0.3d |
| 4 | **汇总行** | `el-table` 的 `show-summary` + `summary-method`，列头右键菜单选择汇总类型（sum/avg/min/max/count），配置存 localStorage | 无 | 0.5d |
| 5 | **行展开子表** | `el-table` 的 `type="expand"` 列，展开行后显示该行全部字段（适用于列数多的宽表场景） | 无 | 0.4d |
| 6 | **TableToolbar 组件封装** | 将列显隐/搜索/拖拽/固定/汇总 UI 抽为 `TableToolbar.vue`，`ReportView` 和 `QueryResult` 共用 | 无 | 0.5d |
| 7 | **导出优化** | 导出请求携带当前列顺序和可见列配置，扩展 `exportExcelAsync` 的可选参数 | `/api/report/excel/async` 新增可选 `columns` 参数 | 0.5d |

### 3.3 关键设计要点

**useTableStorage composable**：
```js
// 核心接口
useTableStorage(tableId) → {
  saveColumnOrder(keys),    // 保存列顺序
  loadColumnOrder(),        // 恢复列顺序
  saveColumnWidth(key, w),  // 保存列宽
  loadColumnWidth(key),     // 恢复列宽
  saveFixedColumn(key, dir),// 保存固定列方向
  loadFixedColumn(key),     // 恢复
  saveSummaryConfig(cols),  // 保存汇总配置
  loadSummaryConfig(),      // 恢复
  clearAll(),               // 清除所有配置
}
```

### 3.4 验收标准

1. 报表页打开 → 拖拽 "天数" 列到第一列 → 刷新页面 → "天数" 列仍在第一列
2. 拖动 "金额" 列头右侧边线加宽 → 刷新页面 → 列宽保持
3. 点击 "门店" 列头悬浮按钮选 "固定到左侧" → 滚动 → 门店列不滚动
4. 右键 "金额" 列头选 "汇总：求和" → 表尾显示总和
5. 点击某一行的展开箭头 → 该行下方展开显示所有字段

---

## 四、1B — 图表增强

### 4.1 影响范围

| 文件 | 当前行数 | 操作 | 说明 |
|------|---------|------|------|
| `frontend/src/components/ChartRenderer.vue` | 913 | 修改 | 增加钻取/DataZoom/数据视图 |
| `frontend/src/utils/echarts.js` | 44 | 修改 | 注册更多图表类型 |
| `frontend/src/views/ChartViewer.vue` | 372 | 修改 | 图表联动 |
| `frontend/src/views/NL2SQLEditor.vue` | 833 | 修改 | 图表联动 |
| `backend/app/schemas/chart.py` | 28 | 修改 | 扩展 ChartConfig |
| `backend/app/services/chart_service.py` | — | 修改 | drill_path 支持 |
| `backend/app/api/charts.py` | — | 修改 | 传递钻取参数 |

### 4.2 任务清单

| # | 任务 | 实现方式 | 后端影响 | 工时 |
|---|------|---------|---------|------|
| 1 | **数据视图** | 在 `toolbox.feature` 中启用 `dataView`，用户可在图表上点击"查看数据"按钮查看原始二维表数据 | 无 | 0.3d |
| 2 | **DataZoom 区域缩放** | 在折线图/散点图的 option 中添加 `dataZoom: [{ type: 'inside' }, { type: 'slider' }]`，按 chartType 条件启用 | 无 | 0.5d |
| 3 | **图表钻取** | `chartClick` 事件 emit 到父组件，父组件修改查询条件后重新请求数据。加面包屑导航显示钻取路径（如 年→月→日） | `ChartRequest` 新增 `drill_path` 字段，`ChartService` 拼入 SQL | 1.5d |
| 4 | **图表联动** | 同一页面多个 ChartRenderer 通过事件总线通信：click 事件触发 `chartSelectionChange`，其他图表据此刷新 | 和钻取共用后端参数扩展 | 0.5d |
| 5 | **图表类型扩展** | 在 `echarts.js` 注册 `HeatmapChart` / `TreemapChart` / `BoxplotChart`，`ChartRenderer` 的 validator 和 option 生成函数对应扩展 | `ChartConfig.chart_type` 的 Literal 类型扩展 | 0.7d |

### 4.3 钻取机制设计

```
用户点击柱状图"2026年1月"柱体
  → ChartRenderer  emit('chartClick', { category: '2026年1月', series: '销售额' })
  → 父组件 收到事件后更新钻取状态
  → 状态变化示例: 钻取路径 ['所有年份', '2026年'] → ['所有年份', '2026年', '1月']
  → 重新调 /api/charts/generate 带 drill_path
  → 后端 ChartService 在原始 SQL 末尾加 WHERE year='2026' AND month='01'
  → 图表渲染日级别数据
  → 面包屑: 所有年份 > 2026年 > 1月 (可点击返回上一级)
```

后端 `ChartService.generate_chart` 改动示例（伪代码）：
```python
def generate_chart(self, request: ChartRequest, user_id: int):
    base_sql = request.sql
    for drill in request.drill_path or []:
        base_sql += f" WHERE {drill.field}='{drill.value}'"
    # 执行 base_sql 获取数据，按 chart_type 封装返回
```

### 4.4 验收标准

1. 折线图右下角显示 "数据视图" 按钮 → 点击后弹窗显示数据表格
2. 折线图可鼠标拖拽缩放区域，下方 slider 可控制显示范围
3. 饼图点击某一扇区 → 钻取到下一级维度的数据 → 面包屑导航可点击回退
4. 柱状图点击某一柱体 → 关联的折线图自动高亮对应数据
5. ���增的 heatmap/treemap/boxplot 图表类型可用

---

## 五、1C — 报表布局器（快速版）

### 5.1 影响范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/components/ReportLayout.vue` | **新建** | 网格布局容器 + 编辑模式 |
| `frontend/src/components/WidgetSlot.vue` | **新建** | 组件工厂，根据类型动态渲染子组件 |
| `frontend/src/components/WidgetAddPanel.vue` | **新建** | 添加组件面板 |
| `frontend/src/composables/useLayoutStorage.js` | **新建** | 布局序列化/恢复 composable |
| `frontend/src/views/Dashboard.vue` | 修改 | 引入 ReportLayout 替代原有 flex 布局 |
| `frontend/src/components/DashboardWidget.vue` | 修改 | 适配新数据模型 |
| `frontend/src/router/index.js` | 修改 | 新增 /dashboard/:id 路由 |
| `backend/app/models/dashboard_widget.py` | 修改 | 新增 grid_x/y/w/h + widget_subtype 字段 |
| `backend/app/schemas/dashboard.py` | 修改 | 新增布局请求/响应 schema |
| `backend/app/services/dashboard_service.py` | 修改 | 新增布局 CRUD |
| `backend/app/api/dashboard.py` | 修改 | 新增布局 API 端点 |
| `frontend/src/api/dashboard.js` | 修改 | 新增布局相关 API 函数 |

### 5.2 任务清单

| # | 任务 | 具体内容 | 工时 |
|---|------|---------|------|
| 1 | **安装依赖** | `npm install grid-layout-plus`（Vue 3 兼容的网格拖拽布局库） | 0.1d |
| 2 | **后端模型扩展** | `DashboardWidgetConfig` 新增 `grid_x/grid_y/grid_w/grid_h/widget_subtype/extra_config` 字段，执行 Alembic migration | 0.5d |
| 3 | **后端 API** | `GET/PUT /api/dashboard/layouts`（列表）、`GET/PUT/DELETE /api/dashboard/layouts/:id`（单个布局）、`POST /api/dashboard/layouts`（新建） | 0.5d |
| 4 | **WidgetSlot 组件工厂** | 接收 `{ type, subtype, config }`，动态渲染 `StatCard / ChartRenderer / QueryResult / NL2SQL 面板 / iframe` 五种组件之一 | 0.5d |
| 5 | **ReportLayout 容器** | 包裹 `grid-layout-plus`，编辑模式下可自由拖拽/调整大小/添加/删除组件，预览模式只读 | 1d |
| 6 | **WidgetAddPanel** | 展示可选组件列表（统计卡/图表/表格/NL2SQL/iframe），拖入布局或点击添加 | 0.3d |
| 7 | **仪表盘整合** | Dashboard.vue 改用 ReportLayout，保留统计数据接口兼容 | 0.5d |
| 8 | **预设布局模板** | 4 种预设：默认看板 / 分析工作台 / 大屏监控 / 空白 | 0.3d |
| 9 | **路由整合** | `/dashboard` 保留，新增 `/dashboard/layouts`（布局列表）、`/dashboard/layouts/:id`（查看）、`/dashboard/layouts/create`（新建） | 0.3d |

### 5.3 数据模型设计

```python
class DashboardWidgetConfig(Base):
    __tablename__ = "dashboard_widget_configs"

    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    widget_type  = Column(String(50), nullable=False)   # stat / chart / table / nl2sql / iframe
    widget_subtype = Column(String(50))                  # 如 chart:line / chart:bar / stat:query_count
    title        = Column(String(100), nullable=False)
    grid_x       = Column(Integer, default=0)
    grid_y       = Column(Integer, default=0)
    grid_w       = Column(Integer, default=4)
    grid_h       = Column(Integer, default=2)
    extra_config = Column(JSON, default={})     # 图表config/data_source_id/SQL等
    visible      = Column(Boolean, default=True)
    layout_id    = Column(Integer, ForeignKey("dashboard_layouts.id", ondelete="CASCADE"))
```

```python
class DashboardLayout(Base):
    __tablename__ = "dashboard_layouts"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name       = Column(String(100), nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### 5.4 WidgetSlot 组件工厂伪代码

```vue
<template>
  <div class="widget-slot" :class="`widget-${type}`">
    <!-- 编辑模式工具栏 -->
    <div v-if="isEditing" class="widget-toolbar">
      <span class="widget-title">{{ title }}</span>
      <el-button-group size="small">
        <el-button @click="remove" type="danger" :icon="Delete" />
      </el-button-group>
    </div>

    <!-- 主体内容，按类型动态渲染 -->
    <StatCard         v-if="type === 'stat'"    :widget-type="subtype" />
    <ChartRenderer    v-if="type === 'chart'"   :chart-type="subtype" :data="data" :config="config" />
    <QueryResult      v-if="type === 'table'"   :data="data" :loading="loading" />
    <!-- nl2sql: 嵌入完整查询面板 -->
    <!-- iframe: 自定义外部嵌入 -->
  </div>
</template>
```

### 5.5 验收标准

1. 进入 `/dashboard/layouts/create` → 空白网格可拖入 "柱状图" 组件 → 柱状图正常渲��
2. 拖拽组件右下角缩放手柄 → 组件宽高变化 → 其他组件自动避让
3. 保存布局 → 刷新页面 → 布局复原
4. 预设模板 "分析工作台" → 一列 NL2SQL 面板 + 一列图表 + 一列表格
5. 编辑模式下可删除组件，预览模式下不可编辑

---

## 六、工时汇总与依赖

| 模块 | 工时 | 可并行 | 前置依赖 |
|------|------|--------|---------|
| **1A 表格增强** | 3d | 是 | 无 |
| **1B 图表增强** | 3.5d | 是 | 1A（共用 ts 组件体系，但可独立开发） |
| **1C 报表布局器** | 4d | 否 | 需 1A+1B 的子组件封装完成 |
| 回归 + 修复 | 1d | — | 三者合并后 |
| **合计 Phase 1** | **~11d** | — | — |

### 并行策略

```
Week 1          Week 2          Week 3
┌─── 1A (3d) ──┐
│               │─── 1B (3.5d) ──┐
│               │                │─── 回归 (1d)
│               │─── 1C (4d) ────┘
└───────────────┘
3人并行: 2-3天完成 Phase 1
1人跟进: 约 11 个工作日
```

---

## 七、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| `sortablejs` 挂载 `el-table` header-row 导致表头点击排序失灵 | 列拖拽与列排序冲突 | 指定 `sortable` 的 `handle` 为专门的拖拽柄列，`el-table-column` 原生排序行为不受影响 |
| `grid-layout-plus` 在 Vue 3 + Element Plus 环境下 resize 事件与 el-table 滚轮事件冲突 | 编辑模式下表格无法滚动 | 编辑模式下 WidgetSlot 内组件 `pointer-events: none`，仅在预览模式可交互 |
| 钻取层数过多导致 Doris 查询性能下降 | 用户钻取 5+ 层后 SQL 越来越复杂 | 默认限制钻取最大 3 层，每层自动加 WHERE 过滤（缩小扫描范围）而非全量 |
| 布局数据模型变更后用户已有配置丢失 | 升级后 Dashboard 白屏 | `dashboard_service._default_configs` 返回兼容旧格式的 widget，无痛迁移 |

---

## 八、当前文件结构快照（用于交叉引用）

### 前端组件
```
frontend/src/components/
├── ChartRenderer.vue      # 图表渲染 (913行)
├── DashboardWidget.vue    # 仪表盘组件 (51行)
├── Header.vue             # 顶部导航
├── Layout.vue             # 整体布局
├── Sidebar.vue            # 侧边栏
├── VirtualScroll.vue      # 虚拟滚动
├── VersionDiff.vue        # 版本比较
└── ExportProgress.vue     # 导出进度

frontend/src/views/
├── Dashboard.vue          # 仪表盘 (331行)
├── ReportView.vue         # 报表/模板结果 (547行)
├── QueryResult.vue        # 查询结果 (185行)
├── ChartViewer.vue        # 图表查看 (372行)
├── NL2SQLEditor.vue       # NL2SQL 编辑器 (833行)
├── QueryEditor.vue        # SQL 查询编辑器
├── AsyncExport.vue        # 异步导出列表
├── TemplateList.vue       # 模板列表
├── TemplateForm.vue       # 模板表单
├── TemplateDetail.vue     # 模板详情
├── TemplateVersion.vue    # 模板版本
├── TemplateVersionHistory.vue
├── TemplateShare.vue      # 模板分享
├── DataSourceList.vue     # 数据源列表
├── DataSourceForm.vue     # 数据源表单
├── MenuList.vue           # 菜单管理
├── SalesForecast.vue      # 销售预测
├── ForecastResultQuery.vue# 预测结果查询
├── ProxyServerList.vue    # 代理服务器列表
├── ProxyServerForm.vue    # 代理服务器表单
├── Login.vue              # 登录
└── AsyncExport.vue        # 异步导出
```

### 后端 API 路由汇总
```
/api/charts        → charts.py    (POST /generate)
/api/query         → query.py     (POST /sql, GET /history)
/api/report        → report.py    (POST /excel, POST /excel/async, POST /pdf)
/api/dashboard     → dashboard.py (GET/PUT /widgets, GET /data, GET/PUT/DELETE /layouts/*)
/api/stats         → stats.py     (GET /dashboard)
```

### 关键数据模型
```
DashboardWidgetConfig (dashboard_widget_configs)
├── id, user_id, widget_type, title, position, visible
├── created_at, updated_at
└── (计划新增: grid_x, grid_y, grid_w, grid_h, widget_subtype, extra_config, layout_id)
```

---

## 九、下一步执行建议

**从 Phase 1A 任务 1 开始。** 这是纯前端改动，1 小时内可看到效果：

1. 安装 `sortablejs`（如果尚未安装）
2. 在 `ReportView.vue` 的 header-row 上挂载 Sortable 实例
3. 实现列顺序的 localStorage 读写
4. 验证：拖拽列 → 刷新页面 → 顺序保持

---

> **文档维护者：** 开发团队
> **更新日志：**
> - v1.0 (2026-05-16) 初始版本，涵盖表格/图表/布局器三个方向的完整开发计划
