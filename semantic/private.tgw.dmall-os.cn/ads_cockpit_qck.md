# 商策快查 NL2SQL 语义层文档

## 数据库概述

- **数据库名**: ads_cockpit_qck（商策快查）
- **数据源**: StarRocks (Apache Doris)
- **用途**: 零售门店快查场景的预聚合数据层，提供销售、成本、库存、供应链、档期促销、会员、门店运营等维度的快速查询。基于订单流水数据进行多口径聚合（销售口径/过账口径）。
- **核心业务概念**:
  - **销售口径 vs 过账口径**: 表名含 `_post_` 的为"过账口径"（已完成财务过账），不含的为"销售口径"（订单完成即计入）
  - **商品级 vs 类目级**: `_item_agg` 为商品粒度，`_ocat_agg` 按营运类目聚合，`_pcat_agg` 按采销类目聚合
  - **agg_level**: 聚合层级，0=门店级、1~5=类目层级、6=商品级
  - **date_type**: 日期类型，1=天、2=周、3=月、31=月累计、51=年累计、5=年
  - **含税 vs 未税**: `_taxed_` 含税金额，`_untaxed_` 未税金额
  - **金额单位:分**: 所有金额字段以"分"为单位，除以100转为"元"
  - **经营方式(sell_type)**: 1=自营、2=联营

---

## 核心主题与表结构

### 主题一：订单流水明细

按订单行记录的流水数据，分为**销售口径**（订单完成时间）和**过账口径**（财务过账时间）。

---

#### 1. ads_cockpit_qck_order_d_v1（流水订单销售表 - 销售口径）

**说明**: 按订单行记录销售数据，订单完成即计入。包含订单维度信息和商品数组。

**数据量**: 大表（按天分区，从2024年1月起）

| 字段 | 类型 | 注释 |
|------|------|------|
| dt | DATE | 日期分区 |
| group_id | BIGINT | 集团ID |
| store_code | VARCHAR(32) | 门店编码 |
| u_id | VARCHAR(128) | 数据唯一键 |
| ht | VARCHAR(4) | 订单完成时段 |
| year_id / quarter_id / month_id / week_id | VARCHAR(8) | 时间编码 |
| order_id_normal | VARCHAR(64) | 订单ID |
| trade_type | VARCHAR(32) | 交易类型 |
| sale_type | VARCHAR(32) | 销售类型 |
| order_origin | INT | 订单来源 |
| source_tag | INT | 下单渠道标识 |
| trade_flag | VARCHAR(32) | 业态 |
| member_flag | INT | 会员标识：0-非会员、1-会员 |
| order_complete_time | VARCHAR(32) | 订单妥投时间（逆向为申请通过时间） |
| posting_time | VARCHAR(32) | 过账、成本核算时间 |
| supplier_code | ARRAY<VARCHAR> | 供应商编码数组 |
| purchase_category1~5_code | ARRAY<VARCHAR> | 采购类目1-5级编码数组 |
| operation_category1~5_code | ARRAY<VARCHAR> | 营运类目1-5级编码数组 |
| brand_id / brand_business_id / brand_flag | ARRAY | 品牌信息数组 |
| super_flag | ARRAY<VARCHAR> | 商品扩展标签数组 |
| service_flag | ARRAY<VARCHAR> | 服务类商品标识数组 |
| matnr | ARRAY<VARCHAR> | 商品编码数组 |
| purchase_combine_category_code | ARRAY<VARCHAR> | 1-5级采销类目拼接组合 |
| operation_combine_category_code | ARRAY<VARCHAR> | 1-5级营运类目拼接组合 |
| user_id_normal | BIGINT | 归一化用户ID |

**主键/Key**: (dt, group_id, store_code, u_id)

**特点**: 商品相关字段为 **ARRAY** 类型（一个订单多个商品），需展开查询。

---

#### 2. ads_cockpit_qck_order_post_d_v1（流水订单销售表 - 过账口径）

**结构与 `order_d_v1` 完全一致**，区别在于数据按**财务过账时间**计入，而非订单完成时间。

---

#### 3. ads_cockpit_qck_order_matnr_d_v1（订单商品维度聚合 - 销售口径）

**说明**: AGGREGATE KEY 模型。按订单-商品维度聚合，支持 BITMAP 去重计数。

**数据量**: 大表（按月分区，AGGREGATE KEY 模型）

| 字段分组 | 字段列表 | 说明 |
|----------|----------|------|
| **维度** | dt, group_id, store_code, u_id | 分区键与唯一标识 |
| **商品信息** | matnr, sell_type, sell_type_name, item_num, ware_name, offline_ware_name | 商品编码、经营方式、名称 |
| **供应商** | supplier_code, supplier_name | 供应商 |
| **类目** | purchase_category1~5 (code+name), operation_category1~5 (code+name) | 采购类目和营运类目1-5级 |
| **时间** | year_id, quarter_id, month_id, week_id | 时间维度 |
| **标签** | trade_type, sale_type, source_tag, trade_flag | 交易/销售类型、渠道、业态 |
| **用户** | user_id_normal (BITMAP) | 归一化用户ID（BITMAP类型） |

**主键/Key (AGGREGATE KEY)**: (dt, group_id, store_code, u_id)

**注意**: AGGREGATE KEY 模型，聚合函数包括 BITMAP_UNION、REPLACE_IF_NOT_NULL。`user_id_normal` 为 BITMAP 类型，使用 `BITMAP_COUNT()` 去重计数。

---

#### 4. ads_cockpit_qck_order_matnr_post_d_v1（订单商品维度聚合 - 过账口径）

**与 `order_matnr_d_v1` 结构一致**，过账口径版本。

---

### 主题二：订单商品聚合（过账口径）

预聚合的商品销售指标，支持商品级和类目级查询。

---

#### 5. ads_cockpit_qck_order_ware_item_agg_d_v1（过账商品销售聚合 - 商品维度）

**说明**: 按商品编码聚合的销售指标，包含商品属性信息。

**数据量**: 大表（按月分区，从2023年1月起）

| 字段分组 | 字段列表 | 说明 |
|----------|----------|------|
| **维度** | dt, group_id, store_code, u_id | 基础维度 |
| **时间** | year_id, quarter_id, month_id, week_id, date_type | 时间维度及日期类型 |
| **标签** | trade_flag, super_flag, member_flag | 业态、商品扩展标签、会员标识 |
| **商品信息** | matnr, sell_type, sell_type_name, status_code, status_name | 商品编码、经营方式、状态 |
| **商品详情** | item_num, ware_name, offline_ware_name, purchase_taxed_price, offline_current_price | 条码、名称、价格 |
| **规格** | spec_type, spec_type_name, spec_qty, spec_unit | 规格信息 |
| **包装** | package_unit, package_num | 包装单位和入数 |
| **供应商** | supplier_code, supplier_name | 供应商 |
| **采购类目** | purchase_category1~5 (code+name) | 采购类目1-5级 |
| **营运类目** | operation_category1~5 (code+name) | 营运类目1-5级 |
| **品牌** | brand_id | 品牌ID |
| **指标** | actual_sale_taxed_amt, actual_sale_untaxed_amt, sale_num, cost_taxed_amt, cost_untaxed_amt, promotion_amt, trade_num, v_actual_sale_untaxed_amt | 销售、成本、促销、交易次数 |

**主键/Key**: (dt, group_id, store_code, u_id)

**指标明细**:

| 指标 | 类型 | 说明 |
|------|------|------|
| actual_sale_taxed_amt | DECIMAL | 商家实销金额(含税)，单位:分 |
| actual_sale_untaxed_amt | DECIMAL | 商家实销金额(未税)，单位:分 |
| sale_num | DOUBLE | 销售数量 |
| cost_taxed_amt | DECIMAL | 销售成本(含税)，单位:分 |
| cost_untaxed_amt | DECIMAL | 销售成本(未税)，单位:分 |
| promotion_amt | DECIMAL | 促销金额，单位:分 |
| trade_num | BIGINT | 交易次数 |
| v_actual_sale_untaxed_amt | DECIMAL | v9实销金额(未税) |

---

#### 6. ads_cockpit_qck_order_ware_ocat_agg_d_v1（过账商品销售聚合 - 营运类目）

**说明**: 按营运类目聚合，包含 agg_level 字段控制聚合层级（0=门店、1~5=类目层级）。

**核心区别**: 不含商品编码，按营运类目+供应商聚合。

| 指标 | 类型 | 说明 |
|------|------|------|
| actual_sale_taxed_amt | DECIMAL | 实销金额(含税) |
| actual_sale_untaxed_amt | DECIMAL | 实销金额(未税) |
| sale_num | DOUBLE | 销售数量 |
| cost_taxed_amt | DECIMAL | 销售成本(含税)，单位:分 |
| cost_untaxed_amt | DECIMAL | 销售成本(未税)，单位:分 |
| refund_sale_num | DOUBLE | 退款数量 |
| refund_actual_sale_taxed_amt | DECIMAL | 退款金额(含税) |
| refund_actual_sale_untaxed_amt | DECIMAL | 退款金额(未税) |
| promotion_amt | DECIMAL | 促销金额，单位:分 |
| sale_item_num | BIGINT | 动销品数 |
| trade_num | BIGINT | 交易次数 |
| total_trade_num | BIGINT | 不区分商品标签的交易次数 |
| v_actual_sale_untaxed_amt | DECIMAL | v9实销金额 |
| promotion_actual_sale_taxed_amt | DECIMAL | 促销实销金额 |
| promotion_actual_sale_untaxed_amt | DECIMAL | 促销未税实销金额 |

**主键/Key**: (dt, group_id, agg_level, store_code, u_id)

---

#### 7. ads_cockpit_qck_order_ware_pcat_agg_d_v1（过账商品销售聚合 - 采销类目）

**与 `ocat_agg` 结构一致**，维度改用采销类目（purchase_category1~5）。

---

#### 8. ads_cockpit_qck_order_ware_post_item_agg_d_v1（过账口径商品销售聚合 - 商品维度）

**与 `order_ware_item_agg` 类似**，增加以下指标：

| 独有指标 | 说明 |
|----------|------|
| promotion_actual_sale_taxed_amt | 促销实销金额(含税) |
| promotion_actual_sale_untaxed_amt | 促销未税实销金额 |
| coupon_actual_sale_taxed_amt | 优惠券实销金额(含税) |
| coupon_actual_sale_untaxed_amt | 优惠券实销金额(未税) |

---

#### 9. ads_cockpit_qck_order_ware_post_ocat_agg_d_v1（过账口径 - 营运类目聚合）

**与 `order_ware_ocat_agg` 结构一致**，增加促销/优惠券指标。

#### 10. ads_cockpit_qck_order_ware_post_pcat_agg_d_v1（过账口径 - 采销类目聚合）

**与 `order_ware_pcat_agg` 结构一致**，增加促销/优惠券指标。

---

### 主题三：门店商品汇总

按门店-商品维度日汇总，包含销售、团购、成本、毛利等。

---

#### 11. ads_cockpit_qck_store_ware_item_agg_d_v1（门店商品日汇总 - 商品维度）

**说明**: 按天、门店、商品维度汇总的宽表，包含销售、团购、成本。

| 字段分组 | 字段列表 | 说明 |
|----------|----------|------|
| **维度** | dt, group_id, store_code, u_id | 基础维度 |
| **时间** | week_id, month_id, quarter_id, year_id, date_type | date_type: 1-天、2-周、3-月、31-月累计、51-年累计、5-年 |
| **商品信息** | matnr, sell_type, sell_type_name, status_code, status_name | 商品基础信息 |
| **商品详情** | item_num, ware_name, offline_ware_name, purchase_taxed_price, offline_current_price | 条码、价格 |
| **规格信息** | spec_type, spec_type_name, classify_type, classify_type_name, spec_qty, spec_unit, package_unit, package_num, ware_taste, basic_unit, basic_unit_desc | 规格、类型、口味、单位 |
| **商品属性** | ware_life, ware_life_unit, estimate_type, estimate_type_name | 保质期、评估类 |
| **供应商** | supplier_code, supplier_name | 供应商 |
| **类目** | purchase_category1~5 (code+name), operation_category1~5 (code+name) | 采购及营运类目1-5级 |
| **品牌** | brand_id, brand_flag | 品牌信息 |
| **销售指标** | ware_amt, sale_num, actual_sale_taxed_amt, actual_sale_untaxed_amt | 金额和销量 |
| **团购指标** | tg_sale_num, tg_actual_sale_taxed_amt, tg_actual_sale_untaxed_amt | 团购相关 |
| **成本指标** | cost_taxed_amt, cost_untaxed_amt, bgp_taxed_amt, bgp_untaxed_amt | 成本与基础毛利 |
| **退货指标** | refund_sale_num, refund_actual_sale_taxed_amt, refund_actual_sale_untaxed_amt | 退货数量/金额 |
| **其他指标** | promotion_amt, sale_item_num, trade_num, v_actual_sale_untaxed_amt | 促销、动销、交易次数 |

**主键/Key**: (dt, group_id, store_code, u_id)

**指标汇总**:

| 指标 | 说明 |
|------|------|
| ware_amt | 商品行总销售金额，单位:分 |
| sale_num | 实销商品数量 |
| actual_sale_taxed_amt | 实销金额(含税)，单位:分 |
| actual_sale_untaxed_amt | 实销金额(未税)，单位:分 |
| tg_sale_num | 团购实销商品数量 |
| tg_actual_sale_taxed_amt | 团购实销金额(含税)，单位:分 |
| tg_actual_sale_untaxed_amt | 团购实销金额(未税)，单位:分 |
| cost_taxed_amt | 销售成本(含税)，单位:分 |
| cost_untaxed_amt | 销售成本(未税)，单位:分 |
| bgp_taxed_amt | 基础毛利(含税)，单位:分 |
| bgp_untaxed_amt | 基础毛利(未税)，单位:分 |
| refund_sale_num | 退款数量 |
| refund_actual_sale_taxed_amt | 退款金额(含税)，单位:分 |
| refund_actual_sale_untaxed_amt | 退款金额(未税)，单位:分 |
| promotion_amt | 促销金额，单位:分 |
| sale_item_num | 动销品数 |
| trade_num | 交易次数 |
| v_actual_sale_untaxed_amt | v9实销金额(未税) |

---

#### 12. ads_cockpit_qck_store_ware_ocat_agg_d_v1（门店商品日汇总 - 营运类目）

**说明**: 按营运类目聚合，agg_level=0 门店级、1~5 类目层级。

| 独有维度/指标 | 说明 |
|------|------|
| agg_level | 集合层级 0-门店 1~5 类目层级 |
| super_flag | 商品扩展标签 |
| brand_name, brand_flag | 品牌名称和标识 |

**指标**: 与 `store_ware_item_agg` 一致，不含商品级字段。

**主键/Key**: (dt, group_id, agg_level, store_code, u_id)

---

#### 13. ads_cockpit_qck_store_ware_pcat_agg_d_v1（门店商品日汇总 - 采销类目）

**与 `ocat_agg` 结构类似**，维度改为采销类目，不含商品级和规格字段。

---

### 主题四：库存汇总

---

#### 14. ads_cockpit_qck_store_ware_stock_item_agg_d_v1（库存日汇总 - 商品维度）

**说明**: 按天、门店、商品维度汇总的库存指标。

**与 `store_ware_item_agg` 共享商品信息字段**，独有指标如下：

| 独有字段 | 说明 |
|----------|------|
| price_group_code, price_group_name | 价格群组 |
| end_stock_num | 期末库存数量 |
| end_stock_taxed_cost | 期末库存成本(含税)，单位:分 |
| end_stock_untaxed_cost | 期末库存成本(未税)，单位:分 |
| map_stock_taxed_cost | 移动平均库存单位成本(含税MAP)，单位:分 |
| map_stock_untaxed_cost | 移动平均库存单位成本(未税MAP)，单位:分 |

---

#### 15. ads_cockpit_qck_store_stock_pcat_agg_d_v1（库存聚合 - 采销类目）

**说明**: 按采销类目聚合的库存数据。

| 指标 | 说明 |
|------|------|
| end_stock_num | 期末数量 |
| end_stock_taxed_cost | 期末含税成本，单位:分 |
| end_stock_untaxed_cost | 期末未税成本，单位:分 |
| map_stock_taxed_cost | 含税移动库存单位成本 |
| map_stock_untaxed_cost | 未税移动库存单位成本 |
| return_stock_num | 退货数量 |
| return_stock_taxed_amt | 供商退货金额(含税)，单位:分 |
| return_stock_untaxed_amt | 供商退货金额(未税)，单位:分 |
| receive_stock_num | 收货数量 |
| receive_stock_taxed_amt | 收货金额(含税)，单位:分 |
| receive_stock_untaxed_amt | 收货金额(未税)，单位:分 |

**主键/Key**: (dt, group_id, agg_level, store_code, u_id)

---

### 主题五：档期促销

---

#### 16. ads_cockpit_qck_store_ware_schedule_item_d_v1（档期商品销售 - 商品维度）

**说明**: 按档期维度汇总的商品销售数据，包含档期信息和销售指标。

| 独有字段 | 说明 |
|----------|------|
| schedule_no | 档期号 |
| schedule_name | 档期名称 |
| schedule_start_time | 档期开始时间 |
| schedule_end_time | 档期结束时间 |

**指标**: 包含销售金额、销量等核心指标。

**主键/Key**: (dt, group_id, store_code, u_id)

---

#### 17. ads_cockpit_qck_store_ware_schedule_pcat_agg_d_v1（档期销售聚合 - 采销类目）

**说明**: 按档期+采销类目聚合，包含更丰富的档期信息。

| 独有字段 | 说明 |
|----------|------|
| schedule_period_time | 档期有效期 |
| schedule_period_days | 档期有效天数 |
| schedule_pos | 档期位置 |
| dn | 档期的第n天 |
| theme_code, theme_name | 主题编码和名称 |
| theme_start_time, theme_end_time | 主题起止时间 |
| promotion_level_code, promotion_level_name | 促销级别 |

**主键/Key**: (dt, group_id, agg_level, store_code, u_id)

---

### 主题六：场景分析

---

#### 18. ads_cockpit_qck_scene_store_ware_ocat_agg_d_v1（场景门店商品分析 - 营运类目）

**说明**: 场景分析预聚合表，包含多数据源标记和多层次成本指标。

| 独有字段 | 说明 |
|----------|------|
| data_source | 数据来源：0-OS标准数据、3-商家历史数据、4-商家定制模型数据 |
| gross_sale_taxed_amt | 含税销售金额（不剔除退货），单位:分 |
| gross_sale_untaxed_amt | 未税销售金额（不剔除退货），单位:分 |
| gross_sale_taxed_cost | 含税销售成本（不剔除退货），单位:分 |
| gross_sale_untaxed_cost | 未税销售成本（不剔除退货），单位:分 |
| gross_sale_num | 商品销售数量（不剔除退货逆向） |
| 其他指标 | ware_amt, sale_num, actual_sale_taxed/untaxed_amt, v_actual_sale_untaxed_amt |

**主键/Key**: (dt, group_id, agg_level, store_code, u_id)

---

#### 19. ads_cockpit_qck_scene_store_ware_pcat_agg_d_v1（场景门店商品分析 - 采销类目）

**与 `scene_ocat_agg` 结构一致**，维度改为采销类目。

---

### 主题七：供应链收货

---

#### 20. ads_cockpit_qck_scm_receive_ware_pcat_agg_d_v1（供应链收货聚合 - 采销类目）

**说明**: 聚焦供应链收货流程，包含订货确认、收货、价格信息。

| 指标 | 说明 |
|------|------|
| receive_taxed_price | 收货单价【含税】 |
| receive_untaxed_price | 收货单价【未税】 |
| purchase_taxed_price | 采销进货价【含税】 |
| purchase_untaxed_price | 采销进货价【未税】 |
| purchase_tax_rate | 进项税税率 |
| purchase_tax_code | 进项税税类型 |
| purchase_tax_amt | 进项税税额 |
| book_confirm_num | 订货确认数量(基本单位) |
| book_confirm_cost_taxed_amt | 订货确认成本(含税) |
| book_confirm_cost_untaxed_amt | 订货确认成本(未税) |
| book_num | 订货数量(基本单位) |
| ... | 等更多SCM指标 |

| 独有维度 | 说明 |
|----------|------|
| po_type | 采购订单类型：0-在库、1-直流sto、2-直送、3-直流cpo、4-so、5-调拨、6-二配STO |
| po_type_name | 采购订单类型名称 |
| inner_supplier_code, inner_supplier_name | 内部供应商 |
| agg_level=6 | 商品级聚合 |

**主键/Key**: (dt, group_id, store_code, u_id)

---

### 主题八：供应商与预算

---

#### 21. ads_cockpit_qck_supplier_store_pcat_agg_d_v1（供应商聚合 - 采销类目）

**说明**: 按供应商+采销类目聚合的销售数据。

| 独有维度 | 说明 |
|----------|------|
| supplier_code, supplier_name | 供应商 |
| inner_supplier_code, inner_supplier_name | 内部供应商 |
| sell_type, sell_type_name | 经营方式 |

**指标**: ware_amt, sale_num, actual_sale_taxed/untaxed_amt, v_actual_sale_untaxed_amt

**主键/Key**: (dt, group_id, agg_level, store_code, supplier_code, u_id)

---

#### 22. ads_cockpit_qck_store_cat_budget_d_v1（类目预算）

**说明**: 门店类目预算表，包含销售额、毛利、库存、商损等多维度预算数据。

| 维度 | 说明 |
|------|------|
| category_type | 类目类型：opt-营运、pur-采销 |
| category1~3 (code+name) | 类目1-3级 |

| 预算指标 | 说明 |
|----------|------|
| taxed_amt_budget | 含税销售额预算 |
| untaxed_amt_budget | 未税销售额预算 |
| ngp_taxed_amt_budget | 含税净毛利预算 |
| ngp_untaxed_amt_budget | 未税净毛利预算 |
| end_inventory_taxed_cost_budget | 含税期末库存成本预算 |
| end_inventory_untaxed_cost_budget | 未税期末库存成本预算 |
| self_sale_taxed_cost_budget | 含税自营销售成本预算 |
| self_sale_untaxed_cost_budget | 未税自营销售成本预算 |
| wl_taxed_amt_budget | 含税商损预算 |
| wl_untaxed_amt_budget | 未税商损预算 |
| discard_taxed_amt_budget | 含税废弃金额预算 |
| discard_untaxed_amt_budget | 未税废弃金额预算 |
| bgp_taxed_amt_budget | 含税基础毛利预算 |
| bgp_untaxed_amt_budget | 未税基础毛利预算 |
| skb_taxed_amt_mtd | 含税赞返月至今 |
| skb_untaxed_amt_mtd | 未税赞返月至今 |
| cgp_taxed_amt_mtd | 含税综合毛利月至今 |
| cgp_untaxed_amt_mtd | 未税综合毛利月至今 |
| taxed_amt_budget_mtd | 销售预算含税月至今 |
| untaxed_amt_budget_mtd | 销售预算未税月至今 |
| ngp_taxed_amt_budget_mtd | 净毛利含税月至今 |
| ngp_untaxed_amt_budget_mtd | 净毛利未税月至今 |
| end_inventory_taxed_cost_budget_mtd | 期末库存成本含税月至今 |
| end_inventory_untaxed_cost_budget_mtd | 期末库存成本未税月至今 |
| bgp_taxed_amt_budget_mtd | 基础毛利含税月至今 |
| bgp_untaxed_amt_budget_mtd | 基础毛利未税月至今 |

**主键/Key**: (dt, group_id, agg_level, category_type, store_code, u_id)

---

#### 23. ads_cockpit_qck_store_cat_ware_budget_d_v1（商品预算）

**说明**: 按商品维度的预算数据。

| 预算指标 | 说明 |
|----------|------|
| actual_sale_taxed_amt_budget | 实销金额预算(含税)，单位:分 |
| actual_sale_untaxed_amt_budget | 实销金额预算(未税)，单位:分 |

---

### 主题九：门店运营

---

#### 24. ads_cockpit_qck_store_activation_agg_d_v1（门店稼动指标）

**说明**: 门店运营效率指标，包含稼动、配送、拣货、天气等。

| 指标 | 说明 |
|------|------|
| activation_cnt | 稼动次数 |
| member_activation_cnt | 会员稼动次数 |
| cancel_numerator / cancel_denominator | 取消率分子/分母 |
| delivery_numerator / delivery_denominator | 配送及时率分子/分母 |
| redelivery_numerator / redelivery_denominator | 配送再投率分子/分母 |
| refund_numerator / refund_denominator | 退款率分子/分母 |
| lackorder_numerator / lackorder_denominator | 缺货率分子/分母 |
| pickorder_numerator / pickorder_denominator | 拣货及时率分子/分母(配送) |
| selforder_numerator / selforder_denominator | 拣货及时率分子/分母(自提) |
| hurlorder_num | 妥投订单数 |
| punctual_numerator / punctual_denominator | 准时率分子/分母 |
| store_area | 门店面积 |
| new_store_flag | 是否新店：1-是、0-否 |
| max_temperature / min_temperature | 当天最高/最低温度 |
| weather | 天气描述 |

**主键/Key**: (dt, group_id, store_code, u_id)

---

### 主题十：异常监控

---

#### 25. ads_cockpit_qck_store_ware_abnormal_d_v1（异常商品明细）

**说明**: 记录异常商品数据，含超时未取、缺货、盘点异常等标签。

**包含维度**: 时间、门店、商品、类目（采购+营运1-5级）

**主键/Key**: (dt, group_id, store_code, u_id)

---

### 主题十一：集团会员

---

#### 26. ads_cockpit_qck_group_d_v1（集团每日指标）

**说明**: 集团级别的会员生命周期指标，按日汇总。

| 指标 | 说明 |
|------|------|
| total_member_num | 累计会员数 |
| new_member_num | 新会员数（近30天注册） |
| active_member_num | 活跃会员数（最近消费<30天） |
| sleep_member_num | 沉睡会员数（30天<=最近消费<90天） |
| lost_member_num | 流失会员数（90天<=最近消费<180天） |
| dead_member_num | 死寂会员数（最近消费>=180天） |
| no_sale_member_num | 未消费会员数 |
| activate_member_num | 激活会员数（未消费→活跃） |
| weak_member_num | 唤醒会员数（沉睡/流失/死寂→活跃） |
| keep_member_num | 未变动会员数 |
| today_register_member_num | 当天注册会员数 |
| today_first_sale_member_num | 首单会员数 |

**主键/Key**: (dt, group_id, u_id)

---

### 主题十二：商品流水

---

#### 27. ads_cockpit_qck_matnr_sale_d_v1（商品销售流水）

**说明**: 商品粒度的销售流水数据，含ARRAY字段（store_code、trade_type等为数组类型）。

**主键/Key**: (dt, group_id, matnr, u_id)

---

### 主题十三：品类概览

---

#### 28. ads_cockpit_qck_ware_pcat_overview（品类概览）

**说明**: 含管理架构和同期对比的品类销售概览。

| 维度字段 | 说明 |
|----------|------|
| store_name | 门店名称 |
| org_code_1~6 / org_name_1~6 | 管理架构1-6级编码+名称 |
| purchase_category_code_1~5 / purchase_category_name_1~5 | 采销类目1-5级 |

| 指标 | 说明 |
|------|------|
| actual_sale_amt_current_stage | 本期实销金额 |
| ticket_num_current_stage | 本期交易次数 |
| ngp_amt_current_stage | 本期净毛利 |
| actual_sale_amt_same_stage | 同期实销金额 |
| ticket_num_same_stage | 同期交易次数 |
| ngp_amt_same_stage | 同期净毛利 |
| actual_sale_amt_mtd_current_stage | 本月至今实销金额 |
| ...更多MTD/同期对比指标 | 月累计和同期对比 |

---

## 维度表

| 表名 | 说明 |
|------|------|
| dim_store | 门店维度表（含门店基本信息） |
| dim_store_ware_os_fit | 门店商品OS适配表 |
| dim_store_ware_os_fit_snap | 门店商品OS适配快照表 |
| dim_date | 日期维度 |
| dim_hour / dim_hour_os | 小时维度 |
| dim_ware_status | 商品状态维度 |
| dim_brand_status | 品牌状态 |
| dim_vender_ware_status | 商家商品状态 |
| dim_promotion_store | 促销门店 |
| dim_schedule_os | 档期信息 |
| dim_store_ware_promotion_item_d_v1 | 促销商品明细 |
| dim_ware_package | 商品包装信息 |
| dim_supplier_contract | 供应商合同 |
| dim_os_store_d_v2 | OS门店信息 |

---

## 表关系

```
维度表                         聚合事实表
──────────────────────────────────────────────────────────
dim_store ───────────────┬──→ store_ware_*_agg          (门店商品汇总)
                         │──→ order_*                   (订单流水+聚合)
                         │──→ store_activation_agg      (门店稼动)
                         │──→ store_cat_budget          (类目预算)
                         │──→ store_stock_pcat_agg      (库存聚合)
                         │──→ ware_pcat_overview        (品类概览)
                         │
dim_ware_status ─────────┤──→ store_ware_item_agg       (商品状态过滤)
dim_brand_status         │──→ order_ware_item_agg       (品牌过滤)
                         │
dim_supplier_contract ───┤──→ supplier_store_pcat_agg   (供应商聚合)
                         │──→ scm_receive_ware_pcat_agg (供应链收货)
                         │
dim_schedule_os ─────────┤──→ store_ware_schedule_*     (档期相关)
dim_promotion_store      │
```

**关联键说明**:
- 所有聚合表通过 (group_id, store_code) 关联门店维度
- 商品维度表通过 matnr（商品编码）关联
- 供应商通过 supplier_code 关联
- 日期通过 dt 或 date_type 关联时间维度

---

## 表命名规范

| 模式 | 含义 | 示例 |
|------|------|------|
| `order_*_d_v1` | 订单级流水表 | order_d_v1, order_post_d_v1 |
| `order_matnr_*_d_v1` | 订单-商品级聚合 | order_matnr_d_v1 |
| `order_ware_*_agg_d_v1` | 商品聚合（商品/类目级） | order_ware_item_agg, order_ware_ocat_agg |
| `order_ware_post_*_agg_d_v1` | 过账口径商品聚合 | order_ware_post_item_agg |
| `store_ware_*_agg_d_v1` | 门店商品汇总 | store_ware_item_agg, store_ware_ocat_agg |
| `store_ware_stock_*_agg_d_v1` | 库存汇总 | store_ware_stock_item_agg |
| `store_ware_schedule_*_d_v1` | 档期相关 | store_ware_schedule_item_d_v1 |
| `scene_store_ware_*_agg_d_v1` | 场景分析 | scene_store_ware_ocat_agg |
| `scm_receive_ware_*_agg_d_v1` | 供应链收货 | scm_receive_ware_pcat_agg |
| `store_cat_budget_d_v1` | 类目预算 | store_cat_budget_d_v1 |
| `store_cat_ware_budget_d_v1` | 商品预算 | store_cat_ware_budget_d_v1 |

---

## 聚合层级选择指南

| agg_level | 说明 | 适用场景 |
|-----------|------|----------|
| 0 | 门店级 | 按门店汇总，不含类目信息 |
| 1~5 | 类目1~5级 | 按对应类目层级汇总 |
| 6 | 商品级 | 按商品编码汇总（仅部分表支持） |

---

## 查询口径选择

| 口径 | 表名特征 | 说明 |
|------|----------|------|
| 销售口径 | `order_d_v1`（无_post_） | 订单完成即计入（妥投时间） |
| 过账口径 | `order_post_d_v1`（含_post_） | 财务过账后计入（过账时间） |
| 门店汇总 | `store_ware_*` | 按天/月等预聚合的店品宽表 |

**建议**: 常规业务分析使用 **过账口径**（数据更准确），实时性要求高的场景使用 **销售口径**。

---

## 业务规则

1. **金额单位**: 所有金额字段单位为"分"，除以100转为"元"
2. **日期字段(dt)**: `int(11)` 类型格式为 YYYYMMDD（如20240510），`date` 类型格式为 YYYY-MM-DD
3. **date_type**: 1=天、2=周、3=月、31=月累计、51=年累计、5=年
4. **agg_level**: 0=门店级、1~5=类目层级、6=商品级（视表而定）
5. **经营方式**: sell_type=1 自营、sell_type=2 联营
6. **会员标识**: member_flag=0 非会员、member_flag=1 会员
7. **BITMAP字段**: 使用 `BITMAP_COUNT()` 函数去重计数
8. **ARRAY字段**: 出现在订单流水表中，使用 `LATERAL VIEW EXPLODE()` 展开

---

## 常用查询示例

### 按商品维度查询

```sql
-- 某门店某天各商品的销售额和销量
SELECT store_code, matnr, ware_name,
       SUM(actual_sale_untaxed_amt)/100 AS sale_amt,
       SUM(sale_num) AS sale_qty
FROM ads_cockpit_qck_store_ware_item_agg_d_v1
WHERE dt = 20240510
  AND group_id = 123
  AND store_code = 'S001'
GROUP BY store_code, matnr, ware_name
ORDER BY sale_amt DESC;
```

### 按类目聚合查询

```sql
-- 按采销类目统计销售额
SELECT purchase_category1_name,
       SUM(actual_sale_untaxed_amt)/100 AS total_amt,
       SUM(trade_num) AS trade_cnt
FROM ads_cockpit_qck_store_ware_pcat_agg_d_v1
WHERE dt >= 20240501 AND dt <= 20240510
  AND group_id = 123
  AND agg_level = 1  -- 一级类目
GROUP BY purchase_category1_name
ORDER BY total_amt DESC;
```

### 过账口径查询

```sql
-- 过账口径的销售数据（带促销和优惠券）
SELECT store_code,
       SUM(actual_sale_untaxed_amt)/100 AS sale_amt,
       SUM(promotion_actual_sale_untaxed_amt)/100 AS promo_amt,
       SUM(coupon_actual_sale_untaxed_amt)/100 AS coupon_amt
FROM ads_cockpit_qck_order_ware_post_item_agg_d_v1
WHERE dt = 20240510
  AND group_id = 123
GROUP BY store_code;
```

### 库存查询

```sql
-- 期末库存
SELECT store_code, matnr, ware_name,
       end_stock_num,
       end_stock_untaxed_cost/100 AS stock_cost
FROM ads_cockpit_qck_store_ware_stock_item_agg_d_v1
WHERE dt = 20240510
  AND group_id = 123
  AND end_stock_num > 0
ORDER BY end_stock_untaxed_cost DESC
LIMIT 20;
```

### 档期促销分析

```sql
-- 某档期各门店销售
SELECT store_code,
       SUM(actual_sale_untaxed_amt)/100 AS sale_amt
FROM ads_cockpit_qck_store_ware_schedule_pcat_agg_d_v1
WHERE schedule_no = 'SCH20240501'
  AND group_id = 123
  AND agg_level = 0  -- 门店级
GROUP BY store_code;
```

### 供应商分析

```sql
-- 各供应商销售排名
SELECT supplier_name,
       SUM(actual_sale_untaxed_amt)/100 AS total_amt
FROM ads_cockpit_qck_supplier_store_pcat_agg_d_v1
WHERE dt >= 20240501 AND dt <= 20240510
  AND group_id = 123
GROUP BY supplier_name
ORDER BY total_amt DESC;
```

### 预算对比

```sql
-- 实际 vs 预算对比
SELECT category1_name,
       SUM(actual_sale_untaxed_amt)/100 AS actual_amt,
       SUM(untaxed_amt_budget)/100 AS budget_amt
FROM ads_cockpit_qck_store_cat_budget_d_v1
WHERE month_id = '202405'
  AND group_id = 123
  AND category_type = 'pur'  -- 采销类目
GROUP BY category1_name;
```

### 会员分析

```sql
-- 集团会员活跃度
SELECT dt,
       total_member_num,
       active_member_num,
       sleep_member_num,
       lost_member_num,
       new_member_num
FROM ads_cockpit_qck_group_d_v1
WHERE dt >= 20240501 AND dt <= 20240510
  AND group_id = 123
ORDER BY dt;
```

### BITMAP 去重查询

```sql
-- 使用 AGGREGATE KEY 表的 BITMAP 字段
SELECT store_code,
       BITMAP_COUNT(user_id_normal) AS user_cnt
FROM ads_cockpit_qck_order_matnr_d_v1
WHERE dt = 20240510
  AND group_id = 123
GROUP BY store_code;
```

### 供应链收货分析

```sql
-- 按供应商统计收货情况
SELECT supplier_name,
       SUM(book_confirm_num) AS confirm_qty,
       SUM(book_confirm_cost_untaxed_amt)/100 AS confirm_cost
FROM ads_cockpit_qck_scm_receive_ware_pcat_agg_d_v1
WHERE dt >= 20240501 AND dt <= 20240510
  AND group_id = 123
GROUP BY supplier_name;
```

---

## 通用WHERE过滤

```sql
-- 基础过滤
WHERE group_id = ?                    -- 集团ID（必须）

-- 时间过滤
  AND dt >= 20240501 AND dt <= 20240510    -- 日期范围

-- 类目层级过滤
  AND agg_level = 1                         -- 1=一级类目

-- 口径选择（过账口径表已限定）
```
