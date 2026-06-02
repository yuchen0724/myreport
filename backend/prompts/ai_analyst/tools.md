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

## generate_chart
单系列: {"chart_type": "bar|line|pie|scatter", "data": [...], "x_axis_field": "...", "y_axis_field": "...", "title": "..."}
多系列: {"chart_type": "line", "data": [...], "x_axis_field": "...", "y_axis_field": "...", "title": "...", "series_fields": ["门店1", "门店2"]}
**重要：生成图表必须调用 generate_chart 工具。禁止只在文字中说"图表已生成"而不实际调用工具。**

## analyze_data
输入: {"data": [...], "columns": [...], "question": "..."}
