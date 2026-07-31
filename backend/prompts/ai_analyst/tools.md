工具参数参考（仅当需要调用工具时参考此处的参数格式）：

## execute_sql
输入: {"sql": "SELECT ...", "data_source_id": {data_source_id}}
- 库名.表名 格式
- Doris 日期: dt >= 20260501
- **高效技巧**: 用 CTE(WITH)、子查询、JOIN 在一个 SQL 中完成多步计算，避免多次 execute_sql

## get_schema
输入: {"data_source_id": {data_source_id}}
可选: "table_name": "表名"

## list_metrics
输入: {"data_source_id": {data_source_id}}

## query_metric
输入: {"metric_key": "gmv", "data_source_id": {data_source_id}, "dimensions": [...], "start_time": "...", "end_time": "...", "filters": {}, "page": 1, "page_size": 50}

## analyze_inventory
用于区间进销存、缺货、积压、滞销和库存平衡分析。必须先通过 get_schema 确认字段。
输入: {"data_source_id": {data_source_id}, "table_name": "库.表", "start_date": "2026-07-01", "end_date": "2026-07-31", "dimensions": ["store_id", "sku_id"], "entity_keys": ["store_id", "sku_id", "batch_id"], "fields": {"date_field": "dt", "closing_stock_field": "end_stock_num", "sales_field": "sale_num", "receipt_field": "receive_num"}, "filters": {}}
**重要：期初和期末由工具选择边界快照，禁止自行对多个日期的库存余额求和。**

## generate_chart
单系列: {"chart_type": "bar|line|pie|scatter", "data": [...], "x_axis_field": "...", "y_axis_field": "...", "title": "..."}
多系列: {"chart_type": "line", "data": [...], "x_axis_field": "...", "y_axis_field": "...", "title": "...", "series_fields": ["门店1", "门店2"]}
**重要：生成图表必须调用 generate_chart 工具。禁止只在文字中说"图表已生成"而不实际调用工具。**

## analyze_data
输入: {"data": [...], "columns": [...], "question": "..."}
