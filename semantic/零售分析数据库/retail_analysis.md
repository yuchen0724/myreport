# Retail Analysis NL2SQL 语义层文档

## 数据库概述

- **数据库名**: retail_analysis (零售分析数据库)
- **用途**: 记录门店、商品、销售、库存、促销等零售业务数据
- **数据量**: 8张表，约5200条记录

---

## 数据统计

| 表名 | 记录数 |
|------|--------|
| stores | 8 |
| categories | 12 |
| products | 20 |
| customers | 100 |
| promotions | 10 |
| dim_date | 1096 |
| inventory | 160 |
| sales | 3910 |

---

## 表结构

### 1. stores (门店表)

**说明**: 存储门店基本信息

| 字段 | 类型 | 注释 |
|------|------|------|
| store_id | INTEGER | 门店ID - 门店唯一标识 |
| store_name | VARCHAR(100) | 门店名称 - 门店全称 |
| city | VARCHAR(50) | 城市 - 门店所在城市 |
| district | VARCHAR(50) | 区县 - 门店所在区县 |
| store_type | VARCHAR(20) | 门店类型 - 如：旗舰店、标准店、社区店 |
| open_date | DATE | 开业日期 - ��店开业时间 |
| area_sqm | NUMERIC | 营业面积 - 门店面积（平方米） |
| manager_name | VARCHAR(50) | 店长姓名 - 门店负责人 |

**样例数据**:
| store_id | store_name | city | district | store_type | area_sqm |
|----------|------------|------|----------|------------|----------|
| 1 | 北京朝阳大悦城店 | 北京 | 朝阳区 | 旗舰店 | 1200 |
| 2 | 上海南京路店 | 上海 | 黄浦区 | 旗舰店 | 1500 |
| 3 | 广州天河城店 | 广州 | 天河区 | 标准店 | 800 |
| 4 | 深圳华强北店 | 深圳 | 福田区 | 标准店 | 600 |
| 5 | 成都春熙路店 | 成都 | 锦江区 | 社区店 | 400 |
| 6 | 杭州西湖店 | 杭州 | 上城区 | 标准店 | 750 |
| 7 | 武汉江汉路店 | 武汉 | 江汉区 | 社区店 | 350 |
| 8 | 西安小寨店 | 西安 | 雁塔区 | 标准店 | 550 |

---

### 2. categories (商品分类表)

**说明**: 存储商品的层级分类信息

| 字段 | 类型 | 注释 |
|------|------|------|
| category_id | INTEGER | 分类ID - 分类唯一标识 |
| category_name | VARCHAR(100) | 分类名称 - 分类中文名称 |
| parent_category_id | INTEGER | 父分类ID - 上级分类的ID，NULL表示顶级分类 |
| level | INTEGER | 分类层级 - 1为一级分类，2为二级分类 |

**分类层���**:
| category_id | category_name | parent | level |
|-------------|---------------|--------|-------|
| 1 | 电子产品 | - | 1 |
| 2 | 手机 | 1 | 2 |
| 3 | 电脑 | 1 | 2 |
| 4 | 家用电器 | - | 1 |
| 5 | 电视 | 4 | 2 |
| 6 | 冰箱 | 4 | 2 |
| 7 | 服装 | - | 1 |
| 8 | 男装 | 7 | 2 |
| 9 | 女装 | 7 | 2 |
| 10 | 食品饮料 | - | 1 |
| 11 | 零食 | 10 | 2 |
| 12 | 饮料 | 10 | 2 |

---

### 3. products (商品表)

**说明**: 存储商品基本信息

| 字段 | 类型 | 注释 |
|------|------|------|
| product_id | INTEGER | 商品ID - 商品唯一标识 |
| product_name | VARCHAR(200) | 商品名称 - 商品全称 |
| category_id | INTEGER | 分类ID - 关联categories表 |
| brand | VARCHAR(100) | 品牌 - 商品品牌 |
| unit_price | NUMERIC | 单价 - 销售单价（元） |
| cost_price | NUMERIC | 成本价 - 进货成本（元） |
| unit | VARCHAR(20) | 单位 - 如：件、个、箱、kg |
| is_active | BOOLEAN | 是否在售 - true为在售，false为下架 |

**样例数据**:
| product_id | product_name | brand | unit_price | cost_price |
|------------|--------------|-------|------------|------------|
| 1 | iPhone 15 Pro | Apple | 8999 | 7500 |
| 2 | 华���Mate 60 | 华为 | 5999 | 4800 |
| 3 | 小米14 | 小米 | 3999 | 3000 |
| 4 | MacBook Pro 14寸 | Apple | 15999 | 13000 |
| 5 | ThinkPad X1 Carbon | 联想 | 9999 | 8000 |
| 6 | 戴尔 XPS 15 | 戴尔 | 12999 | 10500 |
| 7 | TCL 65寸电视 | TCL | 3999 | 2800 |
| 8 | 海信 75寸电视 | 海信 | 4999 | 3500 |
| 9 | 海尔对开门冰箱 | 海尔 | 5999 | 4200 |
| 10 | 美的变频冰箱 | 美的 | 3999 | 2800 |
| 11 | 优衣库纯棉T恤 | 优衣库 | 99 | 50 |
| 12 | 海澜之家衬衫 | 海澜之家 | 199 | 100 |
| 13 | ZARA连衣裙 | ZARA | 299 | 150 |
| 14 | UR休闲裤 | UR | 259 | 130 |
| 15 | 三只松鼠坚果礼盒 | 三只松鼠 | 128 | 60 |
| 16 | 良品铺子零食包 | 良品铺子 | 68 | 30 |
| 17 | 农夫山泉矿泉水 | 农夫山泉 | 2 | 0.8 |
| 18 | 可口可乐 | 可口可乐 | 3 | 1.2 |
| 19 | 星巴克咖啡 | 星巴克 | 35 | 15 |
| 20 | 小米手环 | 小米 | 299 | 180 |

---

### 4. customers (客户表)

**说明**: 存储客户基本信息

| 字段 | 类型 | 注释 |
|------|------|------|
| customer_id | INTEGER | 客户ID - 客户唯一标识 |
| customer_name | VARCHAR(100) | 客户姓名 - 客户名称 |
| gender | VARCHAR(10) | 性别 - 男/女 |
| age | INTEGER | 年龄 - 客户年龄 |
| member_level | VARCHAR(20) | 会��等级 - 普通会员/银卡会员/金卡会员/钻石会员 |
| register_date | DATE | 注册日期 - 客户首次注册日期 |
| phone | VARCHAR(20) | 联系电话 |

**会员等级**: 普通会员、银卡会员、金卡会员、钻石会员

---

### 5. dim_date (日期维度表)

**说明**: 用于数据分析的日期维度（2023-2025年）

| 字段 | 类型 | 注释 |
|------|------|------|
| date_id | DATE | 日期ID - 主键，格式YYYY-MM-DD |
| year | INTEGER | 年份 - 如2024 |
| quarter | INTEGER | 季度 - 1-4 |
| month | INTEGER | 月份 - 1-12 |
| month_name | VARCHAR(20) | 月份名称 - 一月、二月... |
| week_of_year | INTEGER | 年中第几周 - 1-53 |
| day_of_week | INTEGER | 周几 - 1-7，1代表周一 |
| day_name | VARCHAR(20) | 星期名称 - 星期一、星期二... |
| is_weekend | BOOLEAN | 是否周末 |
| is_holiday | BOOLEAN | 是否节假日 |
| holiday_name | VARCHAR(100) | 节假日名称 - 春节、国庆节... |

**2024年1月1日示例**:
- date_id: 2024-01-01, year: 2024, quarter: 1, month: 1, month_name: 一月
- week_of_year: 1, day_of_week: 1, day_name: 星期一
- is_weekend: false, is_holiday: true, holiday_name: 元旦

---

### 6. promotions (促销活动表)

**说明**: 存储促销活动信息

| 字段 | 类型 | 注释 |
|------|------|------|
| promotion_id | INTEGER | 促销ID - 唯一标识 |
| promotion_name | VARCHAR(200) | 促销名称 |
| start_date | DATE | 开始日期 |
| end_date | DATE | 结束日期 |
| discount_rate | NUMERIC | 折扣率 - 0.8表示8折 |
| discount_amount | NUMERIC | 减免金额（元） |
| promotion_type | VARCHAR(20) | 促销类型 - 折扣/满减/买赠 |

**2024年促销活动**:
| promotion_id | promotion_name | start_date | end_date | discount_rate | type |
|--------------|----------------|------------|----------|---------------|------|
| 1 | 新年大促 | 2024-01-01 | 2024-01-07 | 0.90 | 折扣 |
| 2 | 春节优惠 | 2024-02-10 | 2024-02-20 | 0.85 | 折扣 |
| 3 | 五一劳动节 | 2024-05-01 | 2024-05-03 | - | 满减 |
| 4 | 618年中大促 | 2024-06-15 | 2024-06-20 | 0.80 | 折扣 |
| 5 | 暑期促销 | 2024-07-01 | 2024-08-31 | 0.95 | 折扣 |
| 6 | 中秋国庆 | 2024-09-15 | 2024-10-07 | 0.88 | 折扣 |
| 7 | 双十一 | 2024-11-01 | 2024-11-11 | 0.75 | 折扣 |
| 8 | 双十二 | 2024-12-01 | 2024-12-12 | 0.80 | 折扣 |
| 9 | 会员日特惠 | 2024-01-01 | 2024-12-31 | 0.92 | 折扣 |
| 10 | 新品上市 | 2024-03-01 | 2024-03-15 | - | 满减 |

---

### 7. sales (销售记录表)

**说明**: 存储销售���易明细

| 字段 | 类型 | 注释 |
|------|------|------|
| sale_id | INTEGER | 销售ID - 唯一标识 |
| store_id | INTEGER | 门店ID - 关联stores表 |
| product_id | INTEGER | 商品ID - 关联products表 |
| customer_id | INTEGER | 客户ID - 关联customers表 |
| sale_date | DATE | 销售日期 |
| quantity | INTEGER | 销售数量 |
| unit_price | NUMERIC | 销售单价（元） |
| total_amount | NUMERIC | 销售总额（元） |
| payment_method | VARCHAR(20) | 支付方式 - 现金/微信/支付宝/银行卡/会员卡 |
| promotion_id | INTEGER | 促销ID - 关联promotions表 |
| salesperson | VARCHAR(50) | 销售员姓名 |

**2024年销售统计**:
- 订单总数: 3910
- 销售总额: ¥45,368,109.34
- 客单价: ¥11,603.10
- 销售商品数: 11684

**月度销售**:
| 月份 | 销售额 |
|------|--------|
| 1月 | ¥2,755,743 |
| 2月 | ¥2,976,321 |
| 3月 | ¥3,743,363 |
| 4月 | ¥3,793,158 |
| 5月 | ¥5,224,251 |
| 6月 | ¥3,401,072 |
| 7月 | ¥4,619,353 |
| 8月 | ¥4,716,301 |
| 9月 | ¥3,646,458 |
| 10月 | ¥3,710,167 |
| 11月 | ¥2,490,142 |
| 12月 | ¥4,291,782 |

**门店销售排名**:
| 门店 | 城市 | 销售额 |
|------|------|--------|
| 武汉江汉路店 | 武汉 | ¥6,192,467 |
| 广州天河城店 | 广州 | ¥5,897,703 |
| 深圳华强北店 | 深圳 | ¥5,760,754 |
| 上海南京路店 | 上海 | ¥5,751,180 |
| 成都春熙路店 | 成都 | ¥5,694,178 |
| 杭州西湖店 | 杭州 | ¥5,472,104 |
| 西安小寨店 | 西安 | ¥5,385,017 |
| 北京朝阳大悦城店 | 北京 | ¥5,214,706 |

**商品销售Top10**:
| 商品 | 品牌 | 销量 | 销售额 |
|------|------|------|--------|
| MacBook Pro 14寸 | Apple | 588 | ¥9,086,942 |
| 戴尔 XPS 15 | 戴尔 | 670 | ¥8,430,091 |
| ThinkPad X1 Carbon | 联想 | 595 | ¥5,746,725 |
| iPhone 15 Pro | Apple | 571 | ¥4,951,370 |
| 华为Mate 60 | 华为 | 564 | ¥3,272,874 |
| 海尔对开门冰箱 | 海尔 | 563 | ¥3,260,336 |
| 海信 75寸电视 | 海信 | 640 | ¥3,089,981 |
| 小米14 | 小米 | 646 | ¥2,494,735 |
| TCL 65寸电视 | TCL | 592 | ¥2,284,898 |
| 美的变频冰箱 | 美的 | 522 | ¥2,005,148 |

---

### 8. inventory (库存表)

**说明**: 存储各门店商品库存信息

| 字段 | 类型 | 注释 |
|------|------|------|
| inventory_id | INTEGER | 库存ID - 唯一标识 |
| store_id | INTEGER | 门店ID - 关联stores表 |
| product_id | INTEGER | 商品ID - 关联products表 |
| quantity | INTEGER | 库存数量 |
| last_update | TIMESTAMP | 最后更新时间 |

**说明**: 每条记录表示某门店的某商品库存量

---

## 表关系

```
stores (8条)
  ├── sales ─── products (20条)
  │          ↑        ↑
  │          │        └── categories (12条)
  │          └── customers (100条)
  │
  └── inventory (160条)

promotions (10条)
  └── sales.promotion_id
```

**外键关系**:
- sales.store_id → stores.store_id
- sales.product_id → products.product_id
- sales.customer_id → customers.customer_id
- sales.promotion_id → promotions.promotion_id
- products.category_id → categories.category_id
- inventory.store_id → stores.store_id
- inventory.product_id → products.product_id

---

## 示例查询 (NL2SQL 对照)

| 自然语言 | SQL |
|----------|-----|
| 今年的销售总额是多少？ | SELECT SUM(total_amount) FROM sales WHERE sale_date >= '2024-01-01' |
| 哪个门店销售额最高？ | SELECT store_id, SUM(total_amount) as total FROM sales GROUP BY store_id ORDER BY total DESC LIMIT 1 |
| iPhone 15 Pro 的销量是多少？ | SELECT SUM(quantity) FROM sales WHERE product_id = 1 |
| 统计各城市的门店数量 | SELECT city, COUNT(*) FROM stores GROUP BY city |
| 查找会员等级为钻石的客户 | SELECT * FROM customers WHERE member_level = '钻石会员' |
| 今天的库存总量 | SELECT SUM(quantity) FROM inventory |
| 本月销售额Top10商品 | SELECT product_id, SUM(total_amount) FROM sales WHERE sale_date >= '2024-01-01' AND sale_date < '2024-02-01' GROUP BY product_id ORDER BY SUM(total_amount) DESC LIMIT 10 |
| 周末 vs 工作日 销售对比 | SELECT is_weekend, SUM(total_amount) FROM sales s JOIN dim_date d ON s.sale_date = d.date_id GROUP BY is_weekend |
| 参与促销活动的订单比例 | SELECT COUNT(*) FILTER (WHERE promotion_id IS NOT NULL) * 100.0 / COUNT(*) FROM sales |
| 各品牌毛利率 | SELECT brand, AVG((unit_price - cost_price) / unit_price * 100) FROM products GROUP BY brand |

---

## 常用维度

- **时间维度**: year, quarter, month, week_of_year, day_of_week, is_weekend, is_holiday, holiday_name
- **地区维度**: city, district
- **门店维度**: store_type, area_sqm, manager_name
- **客户维度**: gender, age, member_level
- **商品维度**: brand, category_id, category_name, unit
- **促销维度**: promotion_type, discount_rate, discount_amount

---

## 常见问题模式

| 用户意图 | 字段/表 | 示例 |
|----------|---------|------|
| 按时间统计 | dim_date (year, month, quarter) | "上月销售额" |
| 按地区统计 | stores (city, district) | "各城市销量" |
| 按门店筛选 | stores (store_name, store_type) | "旗舰店业绩" |
| 按商品筛选 | products (product_name, brand, category_id) | "苹果产品销量" |
| 按客户分析 | customers (member_level, gender, age) | "会员消费分析" |
| 促销活动 | promotions (promotion_name, promotion_type) | "双十一活动效果" |
| 库存查询 | inventory (quantity) | "缺货商品" |
| 同比环比 | dim_date (year, quarter, month) | "同比增长" |