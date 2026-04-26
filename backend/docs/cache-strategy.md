# 查询结果缓存策略

## 概述

本系统实现了基于Redis的查询结果缓存策略，用于提高重复查询的性能，减少数据库负载。

## 缓存服务

### CacheService

缓存服务提供以下功能：

- **缓存查询结果**：将SQL查询结果缓存到Redis
- **获取缓存**：根据SQL和参数从Redis获取缓存结果
- **删除缓存**：删除特定查询的缓存
- **批量清除**：根据模式批量清除缓存
- **统计信息**：获取缓存使用统计

### 缓存键生成

缓存键使用以下规则生成：

```
query_result:{md5(sql + params)}
```

其中：
- `sql`：SQL语句
- `params`：查询参数（JSON格式，排序后）
- `md5`：MD5哈希

## 使用方法

### 在查询服务中使用

```python
from app.services.cache_service import cache_service

# 尝试从缓存获取
cached_result = cache_service.get(sql, params)
if cached_result:
    return SQLQueryResponse(**cached_result["result"])

# 执行查询
result = execute_query(sql, params)

# 缓存结果（5分钟）
cache_service.set(sql, result.dict(), params=params, ttl=300)
```

### 通过API管理缓存

#### 获取缓存统计

```bash
GET /api/cache/stats
```

响应：
```json
{
  "status": "connected",
  "total_keys": 100,
  "query_cache_count": 50,
  "memory_used": "10.5M"
}
```

#### 清除缓存

```bash
POST /api/cache/clear?pattern=query_result:*
```

#### 删除特定查询缓存

```bash
DELETE /api/cache/query?sql=SELECT * FROM users
```

## 缓存策略

### 默认TTL

- 查询结果缓存：5分钟（300秒）
- 可根据查询类型和数据更新频率调整

### 缓存失效

- TTL过期自动失效
- 手动删除缓存
- 批量清除缓存

### 缓存适用场景

**适合缓存**：
- 重复执行的查询
- 数据更新不频繁的查询
- 计算成本高的查询

**不适合缓存**：
- 实时性要求高的查询
- 频繁更新的数据
- 个性化查询结果

## 配置

在 `app/config.py` 中配置Redis连接：

```python
# Redis配置
redis_host: str = "localhost"
redis_port: int = 6379
redis_db: int = 0
```

## 监控

### 缓存命中率

可以通过缓存统计信息监控缓存命中率：

```python
stats = cache_service.get_stats()
hit_rate = stats["query_cache_count"] / stats["total_keys"]
```

### 缓存大小

监控Redis内存使用情况：

```python
stats = cache_service.get_stats()
memory_used = stats["memory_used"]
```

## 最佳实践

1. **合理设置TTL**：根据数据更新频率设置合适的过期时间
2. **监控缓存效果**：定期检查缓存命中率和内存使用
3. **及时清理**：对于不再需要的缓存及时清理
4. **避免缓存过大**：对于大结果集考虑分页或限制缓存
5. **处理缓存失效**：在数据更新时主动清除相关缓存

## 故障处理

### Redis连接失败

当Redis连接失败时，缓存服务会自动降级，不影响正常查询功能：

```python
if not cache_service.redis_client:
    # 直接执行查询，不使用缓存
    result = execute_query(sql, params)
```

### 缓存读取失败

缓存读取失败时，会自动执行查询并返回结果：

```python
cached_result = cache_service.get(sql, params)
if cached_result:
    return cached_result
# 缓存读取失败，执行查询
result = execute_query(sql, params)
```

## 测试

运行缓存服务测试：

```bash
pytest tests/test_cache_service.py -v
```

注意：部分测试需要Redis连接，如果Redis未连接会被跳过。
