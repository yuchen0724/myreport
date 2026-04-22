# 性能优化指南

## 缓存策略

### 查询结果缓存
- 查询结果自动缓存 5 分钟
- 缓存键基于数据源 ID、SQL 和参数生成
- 相同查询直接返回缓存结果，提升响应速度

### 模板配置缓存
- 模板配置自动缓存
- 缓存时间：1 小时
- 模板更新后自动清除缓存

### 缓存管理

#### 手动清除缓存
```python
from app.services.cache_service import cache_service

# 清除特定数据源的查询缓存
cache_service.clear_query_cache(data_source_id=1)

# 清除所有查询缓存
cache_service.clear_query_cache()

# 清除特定模板的缓存
cache_service.clear_template_cache(template_id=1)

# 清除所有模板缓存
cache_service.clear_template_cache()
```

#### 缓存键生成
```python
# 查询缓存键
cache_key = cache_service.generate_query_key(
    data_source_id=1,
    sql="SELECT * FROM users",
    params={"limit": 100}
)

# 模板缓存键
cache_key = cache_service.generate_template_key(template_id=1)
```

## 查询优化

### 自动优化
系统会自动对 SQL 查询进行优化：

1. **添加 LIMIT 子句**
   - 如果 SQL 没有 LIMIT，自动添加 `LIMIT 100000`
   - 防止查询返回过多数据

2. **移除注释**
   - 移除 `--` 单行注释
   - 移除 `/* */` 多行注释

3. **标准化关键字**
   - 统一 SQL 关键字大小写
   - 提升可读性

4. **移除多余空格**
   - 压缩 SQL 中的空格
   - 减少传输大小

### 查询验证
系统会验证 SQL 查询的安全性：

- 禁止使用 `DROP`、`DELETE`、`UPDATE`、`INSERT`、`ALTER`、`CREATE`、`TRUNCATE`
- 禁止使用 SQL 注释
- 禁止使用多语句（分号）

### 查询成本估算
系统会估算查询成本：

```python
from app.utils.query_optimizer import QueryOptimizer

cost = QueryOptimizer.estimate_query_cost(sql)

# 成本说明：
# - JOIN: +100
# - GROUP BY: +50
# - ORDER BY: +30
# - HAVING: +20
# - 每个 FROM: +10

# 如果成本 > 200，建议使用异步导出
```

## 限流策略

### 限流规则
- 每分钟最多 100 次请求
- 超过限制返回 429 状态码
- 响应头包含限流信息

### 响应头
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
```

### 限流键
- 使用客户端 IP 地址作为限流键
- 格式：`rate_limit:{client_ip}`

### 自定义限流
```python
from app.middleware.rate_limit import RateLimiter

# 创建自定义限流器
limiter = RateLimiter()
limiter.max_requests = 50  # 每分钟 50 次
limiter.window = 60  # 时间窗口 60 秒

# 检查是否允许请求
if limiter.is_allowed("custom_key"):
    # 处理请求
    pass
else:
    # 返回限流错误
    pass
```

## 性能监控

### 查询执行时间
每次查询都会记录执行时间，可以在查询历史中查看。

### 慢查询识别
- 执行时间 > 5 秒的查询会被标记为慢查询
- 建议优化慢查询的 SQL

### 缓存命中率
- 可以通过 Redis 监控查看缓存命中率
- 建议缓存命中率 > 80%

## 优化建议

### 1. 使用索引
- 为常用查询字段添加索引
- 避免全表扫描

### 2. 优化 SQL
- 避免 `SELECT *`
- 使用具体的字段列表
- 合理使用 WHERE 条件

### 3. 分页查询
- 使用 LIMIT 和 OFFSET 进行分页
- 避免一次性查询大量数据

### 4. 使用异步导出
- 大数据量导出使用异步模式
- 避免阻塞主线程

### 5. 合理使用缓存
- 相同查询会自动缓存
- 避免频繁修改查询参数

## 故障排查

### 查询慢
- 检查是否有索引
- 检查 SQL 是否优化
- 检查数据量是否过大
- 考虑使用异步导出

### 缓存不生效
- 检查 Redis 是否正常运行
- 检查缓存键是否正确
- 检查缓存是否过期

### 频繁触发限流
- 检查是否有循环请求
- 优化请求频率
- 考虑使用批量接口
