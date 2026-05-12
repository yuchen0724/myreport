# 商策自由查 NL2SQL 语义层文档

## 数据库概述

- **数据库名**: ads_cockpit_freedom（商策自由查）
- **数据源**: StarRocks (Apache Doris)
- **用途**: 零售门店商品销售、供应链、库存、贸易质检等业务分析。
- **【重要】跨库查询**: 以下维度表**不在本数据库中**，需要跨库查询：
  - `ads_cockpit_qck.dim_store` - 门店维度表（门店主数据），如需店名请使用此表
  - `ads_cockpit_qck.dim_date` - 日期维度
  - `ads_cockpit_qck.dim_ware_status` - 商品状态维度
  - 使用示例: `SELECT s.store_name FROM ads_cockpit_freedom.ads_cockpit_fd_store_ware_d f LEFT JOIN ads_cockpit_qck.dim_store s ON f.store_code = s.store_code`
- **核心业务概念**:
  - **店品**: 门店与商品的交叉维度，每条记录表示某门店某商品在某个日期的汇总数据
  - **经营方式(sell_type)**: 区分自营(1)、联营(2)等经营模式
  - **实销 vs 销售**: "实销"是实际卖给顾客的数量/金额，"销售"包含实销+退货
  - **含税 vs 未税**: `_taxed_amt`含税金额，`_untaxed_amt`未税金额
  - **金额单位:分**: 所有金额字段以"分"为单位，除以100转为"元"

---

## 表结构

### 维度表

---

#### 1. ads_fd_dim_store_ware（门店商品维度表）

**说明**: 预检店品范围表，记录哪些门店经营哪些商品的基础信息。用于查询前校验门店-商品关系。

**数据量**: 中等规模，全量门店-商品关系

| 字段 | 类型 | 注释 |
|------|------|------|
| group_id | BIGINT | 集团ID |
| store_code | VARCHAR(32) | 门店编码 |
| matnr | VARCHAR(32) | 商品编码 |
| group_tree_code1 ~ name6 | VARCHAR(128) | 管理架构1-6级（编码+名称），组织的管理归属层级 |
| manage_type | INT | 门店经营性质 |
| store_type | INT | 门店类型 |
| store_business_district | VARCHAR(128) | 商圈性质 |
| supplier_code | VARCHAR(32) | 供应商编码 |
| sell_type | INT | 经营方式：1-自营、2-联营 |
| u_id | VARCHAR(128) | 数据唯一键 |
| sell_type_name | VARCHAR(128) | 经营方式名称 |
| status_code | VARCHAR(32) | 商品状态编码 |
| status_name | VARCHAR(128) | 商品状态名称：正常销售、停售等 |
| item_num | VARCHAR(32) | 商品国条码 |
| ware_name | VARCHAR(500) | 商品名称 |
| supplier_name | VARCHAR(128) | 供应商名称 |
| brand_flag | VARCHAR(128) | 品牌标识 |
| purchase_category1_code~5 | VARCHAR(32) | 采购类目1-5级编码 |
| purchase_category1_name~5 | VARCHAR(128) | 采购类目1-5级名称 |
| operation_category1_code~5 | VARCHAR(32) | 营运类目1-5级编码 |
| operation_category1_name~5 | VARCHAR(128) | 营运类目1-5级名称 |
| exclude_flag | INT | 业绩排除标识：1-排除、0-不排除 |
| service_flag | INT | 服务商品标识：1-服务商品、0-非服务商品 |
| shopping_bag_flag | INT | 购物袋标识：1-购物袋、0-非购物袋 |

**主键/Key**: (group_id, store_code, matnr) — **不含日期，静态维度表**

**典型用途**:
- 查询某门店经营的所有商品范围
- 按管理架构/采购类目/营运类目过滤门店商品
- 过滤排除商品(exclude_flag=1)、服务商品(service_flag=1)、购物袋(shopping_bag_flag=1)

---

#### 2. ads_fd_dim_supplier（供应商维度表）

**说明**: 供应商基础信息表。记录集团所有供应商的详细资料。

**数据量**: 小型维度表

| 字段 | 类型 | 注释 |
|------|------|------|
| group_id | INT | 集团ID |
| supplier_code | VARCHAR(65533) | 供应商编码 |
| group_name | VARCHAR(65533) | 集团名称 |
| company_id | INT | 公司ID |
| company_name | VARCHAR(65533) | 公司名称 |
| company_short_name | VARCHAR(65533) | 公司简称 |
| supplier_account | VARCHAR(65533) | 供应商账号 |
| supplier_name | VARCHAR(65533) | 供应商名称 |
| supplier_short_name | VARCHAR(65533) | 供应商简称 |
| supplier_type | INT | 供应商类型 |
| supplier_biz_type | VARCHAR(65533) | 供应商业务类型 |
| supplier_tax_type | VARCHAR(65533) | 供应商税类型 |
| supplier_sell_type | INT | 供应商经营类型 |
| supplier_status | INT | 供应商状态 |
| supplier_contact | VARCHAR(65533) | 供应商联系人 |
| supplier_telphone | VARCHAR(65533) | 供应商联系人电话 |
| supplier_address | VARCHAR(65533) | 供应商联系地址 |
| supplier_email | VARCHAR(65533) | 供应商联系邮箱 |
| supplier_postcode | VARCHAR(65533) | 供应商邮政编码 |
| supplier_sign_email | VARCHAR(65533) | 签章邮箱 |
| supplier_sign_mobile | VARCHAR(65533) | 签章手机号 |
| supplier_pay_way | INT | 付款方式 |
| settle_company | VARCHAR(65533) | 结算公司编码 |
| settle_company_name | VARCHAR(65533) | 结算公司名称 |
| supplier_origin | INT | 注册来源 |
| social_credit_code | VARCHAR(65533) | 统一社会信用编码 |
| taxpayer_number | VARCHAR(65533) | 纳税人识别号 |
| taxpayer_type | VARCHAR(65533) | 纳税类型 |
| settle_period | INT | 结算周期 |
| settle_type | INT | 结算方式 |
| settle_start_day | INT | 账期起算日 |
| supplier_can_order_flag | INT | 能否订货标识 |
| supplier_can_return_flag | INT | 能否退货标识 |
| supplier_order_week | VARCHAR(65533) | 订货周日历 |
| create_time | VARCHAR(65533) | 创建时间 |
| update_time | VARCHAR(65533) | 更新时间 |
| supplier_vlt | VARCHAR(65533) | 供应商供货天数 |
| main_supplier_code | VARCHAR(65533) | 父供应商编码 |
| main_supplier_name | VARCHAR(65533) | 父供应商名称 |
| company_manage_mode | INT | 公司经营模式 |

**主键/Key**: (group_id, supplier_code)

---

### 事实表

---

#### 3. ads_cockpit_fd_store_ware_d（店品日汇总宽表）

**说明**: 核心业务表。按天、门店、商品维度汇总的销售、成本、毛利、库存、损耗、供应链等全指标宽表。仅限**自营+联营**门店商品数据，不包含预购、拼团等。注意：表中`_57362`和`_812`后缀的表结构与本表完全一致，仅数据范围不同。

**数据量**: 大表（多分区，按月分区，从2023年1月起）

**分区**: 按`dt`(年月int)分区，如p202301=p202301

| 字段分组 | 字段列表 | 说明 |
|----------|----------|------|
| **维度** | dt(INT), group_id(BIGINT), store_code, matnr, supplier_code, sell_type, u_id, week_id, month_id, quarter_id, year_id, date_type(VARCHAR(8)) | 日期、门店、商品、供应商、经营方式标识 |
| **时间维度** | week_id, month_id, quarter_id, year_id, date_type | date_type(VARCHAR(8)),取值: 1-天、2-周、3-月、31-月累计、51-年累计、5-年 |
| **门店属性** | store_type, sell_type_name | 门店类型、经营方式名称 |
| **商品属性** | status_code, status_name, item_num, ware_name, purchase_taxed_price, offline_current_price, offline_original_price, ware_tax_rate, order_sched_binary, supplier_name, brand_flag | 商品基础信息、价格、税率 |
| **商品类目** | purchase_category1~5(code+name), operation_category1~5(code+name) | 采购类目(5级)和营运类目(5级) |
| **销售指标** | sale_ware_unit, ware_num, sale_num, actual_sale_taxed_amt, actual_sale_untaxed_amt | 销售单位、销售数量、实销数量、实销金额(含税/未税) |
| **成本指标** | cost_taxed_amt, cost_untaxed_amt | 销售成本(含税/未税) |
| **退货指标** | refund_sale_num, refund_ware_amt, refund_actual_sale_taxed_amt, refund_actual_sale_untaxed_amt | 退货数量、金额 |
| **毛利指标** | bgp_taxed_amt/untaxed_amt, gp_taxed_amt/untaxed_amt, ngp_taxed_amt/untaxed_amt, gpc_taxed_amt/untaxed_amt, cgp_taxed_amt/untaxed_amt, wgp_taxed_amt/untaxed_amt | 基础毛利、毛利额、净毛利、毛利补偿、综合毛利、商品毛利（均含税/未税） |
| **成本差异** | pcd_taxed_amt/untaxed_amt(采购成本差异), ccd_taxed_amt/untaxed_amt(联营成本差异) | 采购与联营成本差异 |
| **返佣** | skb_taxed_amt/untaxed_amt | 赞助返佣金额 |
| **日均销量** | dms, dms_n, dms_p | 日均销量(总/正常品/促销品) |
| **订货(SCM)** | scm_book_unit, scm_book_num, scm_book_taxed_amt, scm_book_untaxed_amt | 订货单位、数量、金额 |
| **损耗指标** | wl_num, wl_taxed_amt/untaxed_amt, discard_num, discard_taxed_amt/untaxed_amt | 商损数量/金额、废弃数量/金额 |
| **报损报溢** | adjust_loss_num, adjust_loss_taxed_amt/untaxed_amt, adjust_profit_num, adjust_profit_taxed_amt/untaxed_amt | 报损/报溢数量金额 |
| **盘点** | check_loss_num, check_loss_taxed_amt/untaxed_amt, check_profit_num, check_profit_taxed_amt/untaxed_amt | 盘亏/盘盈数量金额 |
| **库存指标** | stock_ware_unit, end_stock_num, end_stock_taxed_cost, end_stock_untaxed_cost, map_stock_taxed_cost, map_stock_untaxed_cost | 库存单位、期末库存数量/成本、移动平均成本 |
| **退货库存** | return_stock_num, return_stock_taxed_amt/untaxed_amt | 供商退货数量/金额 |
| **收货库存** | receive_stock_num, receive_stock_taxed_amt/untaxed_amt | 供商收货数量/金额 |
| **在途待确认** | scm_on_confirm_num, scm_on_way_num, scm_receive_num | 待确认/在途/代收数量 |
| **促销/档期** | promotion_actual_sale_taxed_amt/untaxed_amt, promotion_sale_num, promotion_amt, promotion_bgp_taxed_amt/untaxed_amt | 促销实销金额/数量/优惠金额/促销基础毛利 |
| **档期/出清** | schedule_actual_sale_taxed_amt/untaxed_amt, schedule_sale_num, schedule_sale_price, clearance_... | 档期销售、出清销售/折损 |
| **末次信息** | last_sale_time, last_receive_time, last_receive_num, last_sale_price, last_purchase_price | 末次销售/收货时间、数量、价格 |
| **预警标识** | extra_stock(高库存), low_stock(低库存), lack_stock(畅缺), stasis_sales(滞销), zero_stock(库零), negative_profit(负毛利), negative_stock(负库存), losing_ware(过季清仓), overdue_ware(临期), none_sales(进货未销) | 均为0/1布尔标识 |
| **高库滞销** | extra_stock_count, extra_stock_cost_taxed/untaxed, stasis_sales_stock_count, stasis_sales_stock_cost_taxed/untaxed | 高库存/滞销库存成本明细 |
| **SL指标** | sl_numerator, sl_denominator | SL分子分母 |
| **滞销库存** | sale_num_flag(动销标识), last_end_stock_num(上期末库存), last_end_stock_taxed_cost/untaxed_cost | 动销标记与上期结转库存成本 |
| **累计成本** | self_stock_cost_taxed_amt_mtd/untaxed_amt_mtd, self_end_stock_taxed_cost_mtd/untaxed_cost_mtd | 自营月累计成本(仅天维度使用) |
| **库凭销售** | sale_stock_num, sale_stock_taxed_cost/untaxed_cost, bom_sale_stock_num, bom_sale_stock_taxed_cost/untaxed_cost | 库凭销售数量/成本、BOM销售数量/成本 |
| **配出返仓** | distribute_out_stock_num, distribute_out_stock_taxed_amt/untaxed_amt | 门店退DC配出数量/成本 |
| **其他** | v_actual_sale_untaxed_amt, sale_ware_tag, exclude_flag, service_flag, shopping_bag_flag | V9实销金额、动销标识、排除/服务/购物袋标识 |

**主键/Key**: (dt, group_id, store_code, matnr, supplier_code, sell_type)

**计算说明**:
- 毛利率 = gp_untaxed_amt / actual_sale_untaxed_amt × 100%
- 动销品 = sale_ware_tag = 1
- 排除商品应过滤: exclude_flag != 1
- 一般应过滤服务商品: service_flag != 1
- 一般应过滤购物袋: shopping_bag_flag != 1

---

#### 4. ads_cockpit_fd_store_ware_trade_qc_d_v5（贸易质检日汇总表）

**说明**: 贸易/质检维度销售汇总表。基于交易来源(sale_source)维度的聚合，含订单级聚合（使用BITMAP）和实销金额汇总。本表是**AGGREGATE KEY**模型，需注意聚合语义。

**数据量**: 大表（按月分区，从2021年1月起）

| 字段 | 类型 | 注释 |
|------|------|------|
| dt | INT | 日期（YYYYMM格式） |
| group_id | BIGINT | 集团ID |
| store_code | VARCHAR(32) | 门店编码 |
| u_id | VARCHAR(65533) | 数据唯一键 |
| year_id | VARCHAR(16) | 年编码 |
| quarter_id | VARCHAR(16) | 季度编码 |
| month_id | VARCHAR(16) | 月编码 |
| week_id | VARCHAR(16) | 周编码 |
| date_type | INT | 日期类型 |
| **sale_source_code1** | VARCHAR(32) | **一级交易类型编码** - 如：线下零售、线上到家等 |
| **sale_source_name1** | VARCHAR(32) | **一级交易类型名称** |
| **sale_source_code2** | VARCHAR(32) | **二级交易类型编码** |
| **sale_source_name2** | VARCHAR(32) | **二级交易类型名称** |
| matnr | VARCHAR(32) | 商品编码 |
| item_num | VARCHAR(32) | 商品国条码 |
| ware_name | VARCHAR(256) | 商品名称 |
| sell_type | INT | 经营方式 |
| sell_type_name | VARCHAR(32) | 经营方式名称 |
| ware_status | VARCHAR(30) | 商品状态编码 |
| ware_status_name | VARCHAR(32) | 商品状态名称 |
| supplier_code | VARCHAR(200) | 供应商编码 |
| supplier_name | VARCHAR(128) | 供应商名称 |
| purchase_category1~5 | 采购类目1-5级 | 与店品表相同 |
| operation_category1~5 | 营运类目1-5级 | 与店品表相同 |
| brand_flag | INT | 商品品牌标识 |
| member_flag | INT | 会员标识 |
| **order_id_normal** | **BITMAP** | **普通订单号**（BITMAP类型，用于COUNT DISTINCT订单数） |
| **schedule_order_id** | **BITMAP** | **档期订单号**（BITMAP类型） |
| **coupon_order_id** | **BITMAP** | **优惠券订单号**（BITMAP类型） |
| **coupon_code** | **BITMAP** | **优惠券code**（BITMAP类型） |
| actual_sale_taxed_amt | DECIMAL | 实销金额含税(分) |
| actual_sale_untaxed_amt | DECIMAL | 实销金额未税(分) |
| sale_num | DOUBLE | 销售商品数量 |
| actual_sale_num | DOUBLE | 实销商品数量 |
| sale_ware_unit | VARCHAR(32) | 销售单位 |
| cost_taxed_amt | DECIMAL | 销售成本含税(分) |
| cost_untaxed_amt | DECIMAL | 销售成本未税(分) |
| actual_cost_taxed_amt | DECIMAL | 实销成本含税(分) |
| actual_cost_untaxed_amt | DECIMAL | 实销成本未税(分) |
| bgp_taxed_amt | DECIMAL | 基础毛利含税(分) |
| bgp_untaxed_amt | DECIMAL | 基础毛利未税(分) |
| coupon_amt | BIGINT | 优惠券优惠金额(分) |
| exclude_flag | INT | 业绩排除标识 |
| service_flag | INT | 服务商品标识 |
| shopping_bag_flag | INT | 购物袋标识 |
| v_actual_sale_untaxed_amt | DECIMAL | V9专用实销金额未税(分) |

**主键/Key (AGGREGATE KEY)**: (dt, group_id, store_code, u_id)

**BITMAP字段说明**: order_id_normal、schedule_order_id、coupon_order_id、coupon_code 为BITMAP类型，需要使用`BITMAP_COUNT()`函数进行去重计数，如 `BITMAP_COUNT(order_id_normal)` 计算订单数。

**与ads_cockpit_fd_store_ware_d的核心区别**: 本表多了**交易来源**维度(sale_source_code1/2, sale_source_name1/2)和**BITMAP订单聚合数据**，适合按交易渠道分析。

---

#### 5. ads_cockpit_fd_supply_ware_d（供应链店品日汇总表）

**说明**: 供应链维度汇总表。聚焦订货、收货、期望到货等供应链指标。

**数据量**: 大表（按月分区，从2022年1月起）

| 字段 | 类型 | 注释 |
|------|------|------|
| dt | INT | 日期分区 |
| group_id | BIGINT | 集团ID |
| store_code | VARCHAR(32) | 门店编码 |
| matnr | VARCHAR(32) | 商品编码 |
| supplier_code | VARCHAR(32) | 供应商编码 |
| sell_type | INT | 经营方式 |
| u_id | VARCHAR(128) | 数据唯一键 |
| week_id | VARCHAR(32) | 周编码 |
| month_id | VARCHAR(32) | 月编码 |
| quarter_id | VARCHAR(32) | 季度编码 |
| year_id | VARCHAR(32) | 年编码 |
| date_type | VARCHAR(8) | 1-天、2-周、3-月、31-月累计、51-年累计、5-年 |
| store_type | INT | 门店类型 |
| sell_type_name | VARCHAR(128) | 经营方式名称 |
| status_code | VARCHAR(32) | 商品状态编码 |
| status_name | VARCHAR(128) | 商品状态名称 |
| item_num | VARCHAR(32) | 商品国条码 |
| ware_name | VARCHAR(500) | 商品名称 |
| supplier_name | VARCHAR(128) | 供应商名称 |
| brand_flag | VARCHAR(128) | 商品品牌标识 |
| purchase_category1~5 | 采购类目1-5级 | 编码+名称 |
| operation_category1~5 | 营运类目1-5级 | 编码+名称 |
| base_unit | VARCHAR(32) | 基本单位 |
| **scm_book_num** | DECIMAL | **当天订货数量** |
| **scm_book_taxed_amt** | DECIMAL | **订货金额含税** |
| scm_book_untaxed_amt | DECIMAL | 订货金额未税 |
| **scm_receive_num** | DECIMAL | **当天收货数量** |
| scm_receive_taxed_amt | DECIMAL | 收货金额含税 |
| scm_receive_untaxed_amt | DECIMAL | 收货金额未税 |
| **expect_book_num** | DECIMAL | **期望日期的订货数量** |
| **actual_receive_num_expect_dt** | DECIMAL | **期望日期到货的实际到货数量** |
| exclude_flag | INT | 业绩排除标识 |
| service_flag | INT | 服务商品标识 |
| shopping_bag_flag | INT | 购物袋标识 |

**主键/Key**: (dt, group_id, store_code, matnr, supplier_code, sell_type)

**核心指标**:
- 订货相关：scm_book_num（当天订货量）、scm_book_taxed_amt（订货金额）
- 收货相关：scm_receive_num（当天收货量）、scm_receive_taxed_amt（收货金额）
- 期望到货：expect_book_num（期望在某天到货的订货量）、actual_receive_num_expect_dt（期望日期实际到了多少）

**与ads_cockpit_fd_store_ware_d的差异**: 供应链表专注订货/收货流程，不含销售金额、毛利、库存等指标。

---

### 同构分表说明

以下表结构与**ads_cockpit_fd_store_ware_d**完全一致，仅数据范围不同：

| 表名 | 用途 |
|------|------|
| ads_cockpit_fd_store_ware_d_57362 | 特定门店(57362)的店品数据 |
| ads_cockpit_fd_store_ware_d_812 | 特定门店(812)的店品数据 |

**查询建议**: 业务查询优先使用`ads_cockpit_fd_store_ware_d`（全量宽表）。如需对比或查看特定门店明细可用分表。

---

## 表关系

```
维度表                         事实表
──────────────────────────────────────────────────
ads_fd_dim_store_ware ──┬──→ ads_cockpit_fd_store_ware_d
(门店商品范围)           │     (店品主数据 - 门店商品的详细信息 - 通过group_id,store_code,matnr关联事实表)
                         │──→ ads_cockpit_fd_store_ware_trade_qc_d_v5
                         │     (贸易质检日汇总)
                         │──→ ads_cockpit_fd_supply_ware_d
                         │     (供应链店品日汇总)
                         │
ads_fd_dim_supplier ─────┘──→ (通过supplier_code关联所有事实表)
(供应商信息)
```

**关联键**:
- 所有事实表通过 (group_id, store_code, matnr, supplier_code, sell_type) 与维度表关联
- 维度表 ads_fd_dim_store_ware 用于: 过滤门店-商品范围、获取类目/品牌等属性
- 维度表 ads_fd_dim_supplier 用于: 获取供应商详细信息（如名称、类型、结算方式等）

---

## 业务规则

1. **排除商品过滤**: 几乎所有业务查询应加 `WHERE exclude_flag != 1` 或 `exclude_flag = 0`
2. **服务商品过滤**: `WHERE service_flag != 1 OR service_flag IS NULL`
3. **购物袋过滤**: `WHERE shopping_bag_flag != 1 OR shopping_bag_flag IS NULL`
4. **金额单位**: 所有金额字段单位为"分"，如需元应除以100（`actual_sale_taxed_amt / 100`）
5. **日期字段(dt)**: 格式为 YYYYMMDD 的整数（如20240510），通常用于分区过滤
6. **date_type**: 1=天、2=周、3=月、31=月累计、51=年累计、5=年
7. **毛利计算**: 毛利额(gp_untaxed_amt) = 实销金额(actual_sale_untaxed_amt) - 成本(cost_untaxed_amt)
8. **动销判断**: sale_ware_tag = 1 表示动销品（有销售的商品）
9. **经营方式**: sell_type = 1 自营, sell_type = 2 联营
10. **预警标识字段为0/1**: extra_stock(高库存)、lack_stock(畅缺)、stasis_sales(滞销)等，1表示是

---

## 常用查询模式

### 按维度查询

| 维度 | 字段 | 对应表 |
|------|------|--------|
| 时间(天) | dt | 所有事实表 |
| 时间(周) | week_id | ads_cockpit_fd_store_ware_d, ads_cockpit_fd_supply_ware_d |
| 时间(月) | month_id | 同上 |
| 门店 | store_code | 所有表 |
| 商品 | matnr, ware_name | 所有表 |
| 供应商 | supplier_code, supplier_name | 所有表 |
| 经营方式 | sell_type, sell_type_name | 所有表 |
| 采购类目 | purchase_category1~5 | 所有表 |
| 营运类目 | operation_category1~5 | 所有表 |
| 品牌 | brand_flag | 所有表 |
| 管理架构 | group_tree_code1~6 | ads_fd_dim_store_ware |
| 交易渠道 | sale_source_code1/2 | ads_cockpit_fd_store_ware_trade_qc_d_v5 |

### 按指标分类

| 指标类别 | 主要字段 | 适用表 |
|----------|----------|--------|
| 销售额 | actual_sale_taxed_amt, actual_sale_untaxed_amt | store_ware_d, trade_qc_d_v5 |
| 销量 | sale_num, ware_num | store_ware_d, trade_qc_d_v5 |
| 毛利 | gp_taxed_amt, gp_untaxed_amt, gp_taxed_rate, gp_untaxed_rate | store_ware_d |
| 退货 | refund_sale_num, refund_actual_sale_taxed_amt | store_ware_d |
| 库存 | end_stock_num, end_stock_taxed_cost | store_ware_d |
| 损耗 | wl_num, wl_taxed_amt | store_ware_d |
| 订货 | scm_book_num, scm_book_taxed_amt | store_ware_d, supply_ware_d |
| 收货 | scm_receive_num, scm_receive_taxed_amt | supply_ware_d |
| 订单数 | BITMAP_COUNT(order_id_normal) | trade_qc_d_v5 |
| 促销销售 | promotion_sale_num, promotion_actual_sale_taxed_amt | store_ware_d |

---

## 示例查询

| 自然语言 | SQL |
|----------|-----|
| 某门店昨天的实销金额和毛利是多少？ | SELECT store_code, SUM(actual_sale_untaxed_amt)/100 AS sale_amt, SUM(gp_untaxed_amt)/100 AS gp_amt FROM ads_cockpit_fd_store_ware_d WHERE dt = 20240509 AND store_code = 'S001' AND exclude_flag != 1 AND group_id = 123 GROUP BY store_code |
| 按采购类目统计本月销售额TOP10 | SELECT purchase_category1_name, SUM(actual_sale_untaxed_amt)/100 AS total_amt FROM ads_cockpit_fd_store_ware_d WHERE month_id = '202405' AND date_type = 1 AND exclude_flag != 1 AND group_id = 123 GROUP BY purchase_category1_name ORDER BY total_amt DESC LIMIT 10 |
| 各门店上月的毛利率排名 | SELECT store_code, SUM(gp_untaxed_amt)/NULLIF(SUM(actual_sale_untaxed_amt),0)*100 AS gp_rate FROM ads_cockpit_fd_store_ware_d WHERE month_id = '202404' AND date_type = 1 AND exclude_flag != 1 AND group_id = 123 GROUP BY store_code ORDER BY gp_rate DESC |
| 当前高库存商品有哪些? | SELECT store_code, matnr, ware_name, end_stock_num FROM ads_cockpit_fd_store_ware_d WHERE dt = 20240509 AND extra_stock = 1 AND exclude_flag != 1 AND group_id = 123 |
| 按交易渠道统计某天各渠道销售额 | SELECT sale_source_name1, SUM(actual_sale_untaxed_amt)/100 AS amt FROM ads_cockpit_fd_store_ware_trade_qc_d_v5 WHERE dt = 20240509 AND exclude_flag != 1 AND group_id = 123 GROUP BY sale_source_name1 |
| 某天各门店的订单数和客单价 | SELECT store_code, BITMAP_COUNT(order_id_normal) AS order_cnt, SUM(actual_sale_untaxed_amt)/100/BITMAP_COUNT(order_id_normal) AS avg_order_amt FROM ads_cockpit_fd_store_ware_trade_qc_d_v5 WHERE dt = 20240509 AND exclude_flag != 1 AND group_id = 123 GROUP BY store_code |
| 某供应商的当天订货量和到货率 | SELECT store_code, matnr, scm_book_num, scm_receive_num, scm_receive_num/NULLIF(scm_book_num,0)*100 AS receive_rate FROM ads_cockpit_fd_supply_ware_d WHERE dt = 20240509 AND supplier_code = 'SUP001' AND group_id = 123 |
| 期望到货准确率 | SELECT SUM(actual_receive_num_expect_dt)/NULLIF(SUM(expect_book_num),0)*100 AS accuracy FROM ads_cockpit_fd_supply_ware_d WHERE expect_book_num > 0 AND group_id = 123 |

---

## 通用WHERE过滤

```sql
-- 基础过滤（建议所有查询加上）
WHERE group_id = ?                    -- 集团ID
  AND exclude_flag != 1               -- 排除业绩排除商品
  AND (service_flag != 1 OR service_flag IS NULL)  -- 排除服务商品
  AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)  -- 排除购物袋

-- 时间过滤
  AND dt >= 20240501 AND dt <= 20240509    -- 日期范围
  -- 或
  AND month_id = '202405'                  -- 指定月份
  -- 或
  AND date_type = 1                        -- 只取天粒度
```
