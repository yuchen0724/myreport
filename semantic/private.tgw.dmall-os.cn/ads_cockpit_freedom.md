# 商策自由查 NL2SQL 语义层文档

## 1. 数据库概述

- **数据库名**: ads_cockpit_freedom（商策自由查）
- **数据源**: StarRocks (Apache Doris)
- **用途**: 零售门店商品销售、供应链、库存、贸易质检等业务分析。
- **适用场景**: 门店经营分析、商品经营分析、库存预警、供应链订货收货、交易渠道分析、毛利分析。
- **不适用场景**: 订单级明细分析、会员行为分析、单据级财务对账、实时交易回溯。
- **金额单位**: 所有金额字段默认以“分”为单位，展示时除以 100 转为“元”。
- **默认口径原则**:
  1. 优先使用语义层文档定义的字段和口径。
  2. 优先使用事实表中已经存在的业务字段，不发明派生字段。
  3. 涉及销售、库存、毛利、订货等指标时，必须先确认是否需要过滤 `exclude_flag`、`service_flag`、`shopping_bag_flag`。
  4. 维度展示时，名称和编码应尽量分列，不要混写。
  5. 需要汇总时先汇总分子/分母，再计算比率，禁止先算比率再平均。
  6. 期初、期末和库存余额属于时间维度半可加指标：同一快照日可按门店、商品等维度汇总，禁止跨 `dt` 直接 `SUM`。
  7. 区间查询的期初取开始日的期初字段；若只有期末快照，则取开始日前最近一个有效 `dt` 的期末值。期末取结束日（或不晚于结束日的最近有效 `dt`）的期末值。
  8. 选择期初/期末边界记录后，再按业务维度汇总。区间内销售、收货、退货等流量指标才可按日累加。

---

## 2. 核心业务概念

### 2.1 业务术语词典

| 术语 | 标准定义 | 对应字段/表 | 易混淆项 |
|------|----------|-------------|----------|
| 店品 | 门店-商品在某一天的经营汇总粒度 | `ads_cockpit_fd_store_ware_d*` | 不等于订单明细 |
| 实销 | 实际卖给顾客的销售口径 | `actual_sale_untaxed_amt` / `actual_sale_taxed_amt` | 不等于含退货的销售 |
| 销售 | 销售口径总称，可能包含不同业务口径 | 依问题选择口径字段 | 不能默认与实销等同 |
| 过账 | 财务过账口径 | 贸易质检表中的过账相关场景 | 不等于订单完成口径 |
| 经营方式 | 门店商品经营模式 | `sell_type`, `sell_type_name` | 不能与门店类型混淆 |
| 动销 | 商品有销售发生 | `sale_ware_tag = 1` | 不是库存变化 |
| 高库存 | 库存高于预警阈值 | `extra_stock = 1` | 不等于库存大于 0 |
| 畅缺 | 库存偏低且供给不足 | `lack_stock = 1` | 不等于缺货 100% |
| 滞销 | 一段时间内销售弱 | `stasis_sales = 1` | 不等于零库存 |
| 临期 | 接近保质期 | `overdue_ware = 1` | 不等于过期 |
| 负毛利 | 毛利为负 | `negative_profit = 1` | 不能用销售额为负代替 |

### 2.2 口径优先级

当用户问法模糊时，优先级建议如下：

1. 语义层明确口径
2. 指标词典默认口径
3. 表字段注释
4. 实时 schema
5. 通用模型常识

---

## 3. 指标词典

### 3.1 销售类指标

| 指标中文名 | 推荐字段 | 默认口径 | 单位 | 是否可加总 | 说明 |
|------------|----------|----------|------|------------|------|
| 销售额 | `actual_sale_untaxed_amt` | 默认未税实销金额 | 分 | 是 | 经营分析默认优先未税口径 |
| 含税销售额 | `actual_sale_taxed_amt` | 含税实销金额 | 分 | 是 | 对账或税务场景使用 |
| 销量 | `sale_num` / `actual_sale_num` | 以表中已定义实销数量字段为准 | 数量 | 是 | 需要根据表粒度选择 |
| 客单价 | `SUM(actual_sale_untaxed_amt)/COUNT(order_id)` 或业务定义 | 先求总额再除以订单数 | 元 | 否 | 不能先均值后平均 |
| 订单数 | `BITMAP_COUNT(order_id_normal)` | 去重订单数 | 单 | 是 | 仅适用于 bitmap 表 |

### 3.2 毛利类指标

| 指标中文名 | 推荐字段 | 默认口径 | 单位 | 是否可加总 | 说明 |
|------------|----------|----------|------|------------|------|
| 毛利额 | `gp_untaxed_amt` | 未税毛利 | 分 | 是 | 默认经营分析口径 |
| 毛利率 | `SUM(gp_untaxed_amt)/NULLIF(SUM(actual_sale_untaxed_amt),0)` | 先汇总再计算 | % | 否 | 禁止行级平均 |
| 基础毛利 | `bgp_untaxed_amt` | 基础毛利未税 | 分 | 是 | 与毛利额口径不同 |
| 综合毛利 | `cgp_untaxed_amt` / `wgp_untaxed_amt` | 按业务定义选择 | 分 | 是 | 必须明确口径 |

### 3.3 库存与预警类指标

| 指标中文名 | 推荐字段 | 默认口径 | 单位 | 是否可加总 | 说明 |
|------------|----------|----------|------|------------|------|
| 期末库存 | `end_stock_num` | 期末库存数量 | 数量 | 时间半可加 | 同一快照日可跨门店/商品加总，禁止跨日期求和 |
| 期末库存成本 | `end_stock_untaxed_cost` / `end_stock_taxed_cost` | 期末库存成本 | 分 | 时间半可加 | 建议统一未税优先；禁止跨日期求和 |
| 高库存 | `extra_stock = 1` | 布尔预警 | 标识 | 否 | 只能做筛选或计数 |
| 低库存 | `low_stock = 1` | 布尔预警 | 标识 | 否 | 只能做筛选或计数 |
| 畅缺 | `lack_stock = 1` | 布尔预警 | 标识 | 否 | 只能做筛选或计数 |
| 滞销 | `stasis_sales = 1` | 布尔预警 | 标识 | 否 | 只能做筛选或计数 |
| 负毛利 | `negative_profit = 1` | 布尔预警 | 标识 | 否 | 只能做筛选或计数 |

### 3.4 供应链类指标

| 指标中文名 | 推荐字段 | 默认口径 | 单位 | 说明 |
|------------|----------|----------|------|------|
| 订货量 | `scm_book_num` | 当天订货数量 | 数量 | 供应链分析用 |
| 订货金额 | `scm_book_untaxed_amt` / `scm_book_taxed_amt` | 订货金额 | 分 | 默认优先未税 |
| 收货量 | `scm_receive_num` | 当天收货数量 | 数量 | 供应链分析用 |
| 收货金额 | `scm_receive_untaxed_amt` / `scm_receive_taxed_amt` | 收货金额 | 分 | 默认优先未税 |
| 期望订货量 | `expect_book_num` | 期望到货相关 | 数量 | 用于到货准确率 |
| 期望到货实际量 | `actual_receive_num_expect_dt` | 期望日期到货的实际数量 | 数量 | 用于到货准确率 |

### 3.5 比率类指标

比率类指标统一遵循：先汇总分子和分母，再计算比值。

| 指标中文名 | 公式 | 说明 |
|------------|------|------|
| 毛利率 | `SUM(gp_untaxed_amt)/NULLIF(SUM(actual_sale_untaxed_amt),0)` | 经营分析默认口径 |
| 到货率 | `SUM(scm_receive_num)/NULLIF(SUM(scm_book_num),0)` | 供应链口径 |
| 期望到货准确率 | `SUM(actual_receive_num_expect_dt)/NULLIF(SUM(expect_book_num),0)` | 期望到货口径 |
| 客单价 | `SUM(actual_sale_untaxed_amt)/NULLIF(BITMAP_COUNT(order_id_normal),0)` | 订单口径表适用 |

### 3.6 区间进销存与库存快照规则

- `begin_*`、`opening_*`、`end_*`、`closing_*`、`*_stock_*` 余额字段默认按时间半可加处理。
- 查询 `[start_dt, end_dt]` 时，期初只取开始边界快照，期末只取结束边界快照；不得把区间内每天的期初或期末相加。
- 表中有明确期初字段时，期初取 `start_dt` 对应记录；只有期末字段时，期初取 `dt < start_dt` 的最近一期期末快照。
- 期末优先取 `end_dt` 对应记录；日期缺失时取 `dt <= end_dt` 的最近一期快照，并在结果说明实际快照日。
- 必须先按门店、商品、批次等事实粒度用 `ROW_NUMBER()` 或最大日期关联选出边界记录，再对同一边界日的不同业务实体求和。
- 销售、采购、收货、退货、调拨等期间发生额是流量指标，可在区间内按日 `SUM`；平均库存需显式计算日快照平均值，不能冒充期初或期末。

---

## 4. 维度词典

### 4.1 时间维度

| 维度 | 字段 | 说明 | 使用建议 |
|------|------|------|----------|
| 天 | `dt` | 日粒度分区字段 | 默认分析粒度 |
| 周 | `week_id` | 周编码 | 周趋势分析 |
| 月 | `month_id` | 月编码 | 月度分析 |
| 季度 | `quarter_id` | 季度编码 | 季度分析 |
| 年 | `year_id` | 年编码 | 年度分析 |
| 日期类型 | `date_type` | 1=天、2=周、3=月、31=月累计、51=年累计、5=年 | 控制聚合层级 |

### 4.2 门店与组织维度

| 维度 | 字段 | 说明 | 规则 |
|------|------|------|------|
| 门店 | `store_code` | 门店编码 | 必要时 join 门店维表补名称 |
| 门店类型 | `store_type` | 门店类型 | 用于筛选门店经营属性 |
| 管理架构 | `group_tree_code1~6` | 组织层级 | 名称和编码最好分列展示 |
| 集团 | `group_id` | 集团 ID | 分表规则的核心条件 |

### 4.3 商品维度

| 维度 | 字段 | 说明 | 规则 |
|------|------|------|------|
| 商品 | `matnr` | 商品编码 | 主键粒度之一 |
| 商品名 | `ware_name` | 商品名称 | 适合展示 |
| 条码 | `item_num` | 商品国条码 | 常与商品编码并列展示 |
| 状态 | `status_code`, `status_name` | 商品状态 | 优先展示名称，编码辅助 |
| 品牌 | `brand_flag` | 品牌标识 | 若需品牌名需明确维表 |
| 经营方式 | `sell_type`, `sell_type_name` | 自营/联营 | 不与门店类型混淆 |
| 类目 | `purchase_category1~5`, `operation_category1~5` | 采购/营运类目 | 按层级下钻 |

### 4.4 供应商维度

| 维度 | 字段 | 说明 | 规则 |
|------|------|------|------|
| 供应商编码 | `supplier_code` | 供应商唯一标识 | 主键维度之一 |
| 供应商名称 | `supplier_name` | 展示名 | 必要时 join 供应商维表 |
| 供应商属性 | 结算方式、类型等 | 供应商详情 | 来自维表 `ads_fd_dim_supplier` |

### 4.5 交易来源维度

| 维度 | 字段 | 说明 | 规则 |
|------|------|------|------|
| 一级交易类型 | `sale_source_code1`, `sale_source_name1` | 如线下零售、线上到家 | 来自 trade_qc 表 |
| 二级交易类型 | `sale_source_code2`, `sale_source_name2` | 更细分渠道 | 仅在 trade_qc 表可用 |

### 4.6 预警维度

| 维度 | 字段 | 说明 | 规则 |
|------|------|------|------|
| 高库存 | `extra_stock` | 0/1 | 仅筛选或计数 |
| 低库存 | `low_stock` | 0/1 | 仅筛选或计数 |
| 畅缺 | `lack_stock` | 0/1 | 仅筛选或计数 |
| 滞销 | `stasis_sales` | 0/1 | 仅筛选或计数 |
| 零库存 | `zero_stock` | 0/1 | 仅筛选或计数 |
| 负毛利 | `negative_profit` | 0/1 | 仅筛选或计数 |
| 负库存 | `negative_stock` | 0/1 | 仅筛选或计数 |
| 临期 | `overdue_ware` | 0/1 | 仅筛选或计数 |
| 进货未销 | `none_sales` | 0/1 | 仅筛选或计数 |

---

## 5. 表与关系

### 5.1 事实表

#### 5.1.1 `ads_cockpit_fd_store_ware_d`

- **说明**: 核心店品日汇总宽表。
- **粒度**: `dt + group_id + store_code + matnr + supplier_code + sell_type`
- **分表规则**: `group_id` 对应后缀表；已知 812、57362 需要使用带后缀表。
  - 812  ->ads_cockpit_fd_store_ware_d_812
  - 57362->ads_cockpit_fd_store_ware_d_57362
  - 其它  ->ads_cockpit_fd_store_ware_d
- **适用场景**: 销售、毛利、库存、预警、类目、供应链综合分析。
- **默认过滤**:
  - `exclude_flag != 1`
  - `service_flag != 1 OR service_flag IS NULL`
  - `shopping_bag_flag != 1 OR shopping_bag_flag IS NULL`

#### 5.1.2 `ads_cockpit_fd_store_ware_trade_qc_d_v5`

- **说明**: 贸易/质检日汇总表。
- **粒度**: `dt + group_id + store_code + u_id`
- **特点**: 含交易来源维度和 bitmap 订单聚合字段。
- **适用场景**: 交易渠道分析、订单数分析、客单价分析。
- **注意**: `order_id_normal`、`schedule_order_id`、`coupon_order_id`、`coupon_code` 都是 bitmap 字段，计数必须用 `BITMAP_COUNT()`。

#### 5.1.3 `ads_cockpit_fd_supply_ware_d`

- **说明**: 供应链店品日汇总表。
- **粒度**: `dt + group_id + store_code + matnr + supplier_code + sell_type`
- **适用场景**: 订货、收货、到货准确率、供应链效率分析。

### 5.2 维表

#### 5.2.0 ads_cockpit_qck.dim_store | 门店维度表（含门店基本信息）

#### 5.2.1 `ads_fd_dim_store_ware`

- **说明**: 门店商品范围及属性维表。
- **用途**: 过滤门店-商品范围、补充类目和品牌属性。
- **关联键**: `(group_id, store_code, matnr)`
- **注意**: 如果要展示门店名，事实表中的 `store_name` 不能默认可直接使用；必须先通过门店维表补齐后再 SELECT。
- **门店名来源**: 门店名称以门店维表为准，不以事实表字段猜测为准。
- **JOIN 规则**: 当结果需要展示门店名时，先按 `(group_id, store_code)` JOIN 门店维表，再使用维表中的 `store_name` 输出；只有在语义层或 schema 明确写出事实表自带 `store_name` 时，才允许直接引用。

#### 5.2.2 `ads_fd_dim_supplier`

- **说明**: 供应商基础信息维表。
- **用途**: 补供应商名称、类型、税务、结算方式等属性。
- **关联键**: `(group_id, supplier_code)`

### 5.3 连接规则

1. 门店-商品范围先判断是否在 `ads_fd_dim_store_ware` 中存在，再进入事实表分析。
2. 供应商属性必须通过 `ads_fd_dim_supplier` 补充，不要从事实表硬猜。
3. 交易来源维度只在 `ads_cockpit_fd_store_ware_trade_qc_d_v5` 中可用，其他表不能直接使用。
4. `group_id` 是分表核心条件，查询时必须先确定再选表。
5. 同名字段跨表不代表同口径，必须按当前表语义层定义解释。

---

## 6. 默认业务规则

### 6.1 默认过滤

几乎所有业务查询默认建议加：

```sql
WHERE group_id = ?
  AND exclude_flag != 1
  AND (service_flag != 1 OR service_flag IS NULL)
  AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
```

### 6.2 时间规则

- `dt` 一般用于日期范围过滤，格式为 `YYYYMMDD` 整数。
- `month_id` 一般用于月汇总，格式如 `202405`。
- `date_type` 用于控制粒度，不同分析必须明确取值。

### 6.3 金额规则

- 金额字段默认单位为“分”。
- 若展示给用户，统一转换为“元”。
- 同一张结果表中不要混用“分”和“元”。

### 6.4 比率规则

- 不能先行级算比率再汇总。
- 必须先汇总分子/分母，再计算比率。
- 分母可能为 0 时必须用 `NULLIF()`。

### 6.5 预警规则

- 预警字段只适合筛选、计数、分组，不适合作为连续数值指标。
- 预警字段含义固定为 0/1。

---

## 7. 查询路由规则

### 7.1 先选表再写 SQL

- 销售、库存、毛利、预警、订货综合分析 -> `ads_cockpit_fd_store_ware_d*`
- 交易来源、订单数、客单价 -> `ads_cockpit_fd_store_ware_trade_qc_d_v5`
- 订货/收货/到货准确率 -> `ads_cockpit_fd_supply_ware_d`

### 7.2 下钻优先级

1. 门店
2. 商品
3. 供应商
4. 类目
5. 交易来源
6. 预警

### 7.3 展示规则

- 名称和编码尽量分列。
- 类目层级要显示明确层级名，不要只给拼接编码。
- 如果用户问“TopN”，默认按目标指标降序。

---

## 8. 示例查询

| 自然语言 | 推荐 SQL 思路 |
|----------|---------------|
| 某门店昨天的实销金额和毛利是多少 | 选 `ads_cockpit_fd_store_ware_d*`，按 `store_code + dt` 汇总 `actual_sale_untaxed_amt` 和 `gp_untaxed_amt` |
| 按采购类目统计本月销售额 TOP10 | 选 `ads_cockpit_fd_store_ware_d*`，按 `purchase_category1_name` 聚合销售额并排序 |
| 各门店上月毛利率排名 | 选 `ads_cockpit_fd_store_ware_d*`，按 `store_code` 汇总分子分母后算毛利率 |
| 当前高库存商品有哪些 | 选 `ads_cockpit_fd_store_ware_d*`，筛 `extra_stock = 1` |
| 按交易渠道统计某天销售额 | 选 `ads_cockpit_fd_store_ware_trade_qc_d_v5`，按 `sale_source_name1` 聚合 |
| 某天各门店订单数和客单价 | 选 `ads_cockpit_fd_store_ware_trade_qc_d_v5`，订单数用 `BITMAP_COUNT(order_id_normal)` |
| 某供应商当天订货量和到货率 | 选 `ads_cockpit_fd_supply_ware_d`，算 `scm_receive_num / scm_book_num` |
| 期望到货准确率 | 选 `ads_cockpit_fd_supply_ware_d`，算 `actual_receive_num_expect_dt / expect_book_num` |

---

## 9. 禁用规则

- 不要把订单数和商品数混为一谈。
- 不要把含税和未税混用。
- 不要把门店名、商品名、供应商名和编码混在一起输出。
- 不要在 bitmap 字段上直接 `COUNT(*)` 代替去重计数。
- 不要把预警字段当连续数值做均值。
- 不要在没有明确 group_id 时随意选错分表。

---

## 10. 维护建议

当新增字段、指标或 join 时，必须同步更新：

1. 指标词典
2. 维度词典
3. 连接规则
4. 默认过滤规则
5. 示例查询

如果后续要接入程序消费，建议把本文件同步输出为：
- `ads_cockpit_freedom.semantic.json`
- `ads_cockpit_freedom.semantic.yaml`

这样 NL2SQL、AI 分析师、RCA、订阅和仪表盘都能直接复用。
