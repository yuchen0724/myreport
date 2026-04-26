# 操作审计日志

## 概述

本系统实现了完整的操作审计日志功能，用于记录用户的所有操作行为，满足合规性和安全审计要求。

## 功能特性

### 1. 自动审计

通过中间件自动记录所有API调用，包括：
- 用户操作（创建、更新、删除、查询）
- 操作时间
- IP地址
- 用户代理
- 操作状态（成功/失败）
- 错误信息

### 2. 审计日志服务

提供以下功能：
- 创建审计日志
- 查询审计日志列表
- 获取审计日志详情
- 用户活动统计
- 系统统计信息

### 3. 审计日志API

提供RESTful API接口：
- `GET /api/audit-logs` - 获取审计日志列表
- `GET /api/audit-logs/{id}` - 获取审计日志详情
- `GET /api/audit-logs/user/{id}/activity` - 获取用户活动统计
- `GET /api/audit-logs/system/stats` - 获取系统统计信息

## 数据模型

### AuditLog

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户ID |
| action | String | 操作类型（CREATE, UPDATE, DELETE, VIEW等） |
| resource_type | String | 资源类型（template, query, data_source等） |
| resource_id | String | 资源ID |
| details | Text | 操作详情（JSON格式） |
| ip_address | String | IP地址 |
| user_agent | String | 用户代理 |
| status | String | 操作状态（success, failure） |
| error_message | Text | 错误信息 |
| created_at | DateTime | 创建时间 |

## 使用方法

### 手动创建审计日志

```python
from app.services.audit_log_service import AuditLogService

audit_service = AuditLogService(db)
audit_service.create_log(
    user_id=user_id,
    action="CREATE",
    resource_type="template",
    resource_id="1",
    details={"name": "测试模板"},
    ip_address="127.0.0.1",
    user_agent="test-agent",
    status="success"
)
```

### 查询审计日志

```python
from app.services.audit_log_service import AuditLogService

audit_service = AuditLogService(db)

# 获取用户的所有日志
logs = audit_service.get_logs(user_id=1)

# 按条件过滤
logs = audit_service.get_logs(
    user_id=1,
    action="CREATE",
    resource_type="template",
    status="success"
)

# 分页查询
logs = audit_service.get_logs(user_id=1, skip=0, limit=100)
```

### 获取用户活动统计

```python
from app.services.audit_log_service import AuditLogService

audit_service = AuditLogService(db)
activity = audit_service.get_user_activity(user_id=1)

print(f"总操作数: {activity['total_actions']}")
print(f"成功率: {activity['success_rate']}")
print(f"操作统计: {activity['action_counts']}")
```

### 获取系统统计

```python
from app.services.audit_log_service import AuditLogService

audit_service = AuditLogService(db)
stats = audit_service.get_system_stats()

print(f"总操作数: {stats['total_actions']}")
print(f"活跃用户数: {stats['active_users']}")
print(f"资源类型统计: {stats['resource_type_counts']}")
```

## API使用示例

### 获取审计日志列表

```bash
GET /api/audit-logs?user_id=1&action=CREATE&limit=10
```

响应：
```json
{
  "logs": [
    {
      "id": 1,
      "user_id": 1,
      "action": "CREATE",
      "resource_type": "template",
      "resource_id": "1",
      "details": {"name": "测试模板"},
      "ip_address": "127.0.0.1",
      "user_agent": "Mozilla/5.0...",
      "status": "success",
      "error_message": null,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

### 获取用户活动统计

```bash
GET /api/audit-logs/user/1/activity
```

响应：
```json
{
  "total_actions": 100,
  "action_counts": {
    "CREATE": 30,
    "UPDATE": 40,
    "DELETE": 10,
    "VIEW": 20
  },
  "success_count": 95,
  "failure_count": 5,
  "success_rate": 0.95
}
```

### 获取系统统计

```bash
GET /api/audit-logs/system/stats
```

响应：
```json
{
  "total_actions": 1000,
  "action_counts": {
    "CREATE": 300,
    "UPDATE": 400,
    "DELETE": 100,
    "VIEW": 200
  },
  "resource_type_counts": {
    "template": 500,
    "query": 300,
    "data_source": 200
  },
  "success_count": 950,
  "failure_count": 50,
  "success_rate": 0.95,
  "active_users": 50
}
```

## 审计中间件

### 自动审计

审计中间件会自动记录所有API调用，无需手动编写审计代码。

### 跳过审计

某些路径不需要审计，可以在中间件中配置：

```python
SKIP_PATHS = {
    "/health",
    "/",
    "/docs",
    "/openapi.json",
    "/api/auth/login",
    "/api/auth/me"
}
```

### 资源类型映射

中间件会根据URL路径自动识别资源类型：

```python
RESOURCE_TYPE_MAP = {
    "/api/templates": "template",
    "/api/query": "query",
    "/api/nl2sql": "nl2sql",
    "/api/data-sources": "data_source",
    "/api/users": "user",
    "/api/reports": "report",
    "/api/charts": "chart"
}
```

## 权限控制

### 普通用户

- 只能查看自己的审计日志
- 可以查看自己的活动统计

### 管理员

- 可以查看所有用户的审计日志
- 可以查看系统统计信息

## 性能优化

### 索引优化

审计日志表已创建以下索引：
- `user_id` - 用户ID索引
- `action` - 操作类型索引
- `resource_type` - 资源类型索引
- `created_at` - 创建时间索引

### 分页查询

使用分页查询避免一次性加载大量数据：

```python
logs = audit_service.get_logs(user_id=1, skip=0, limit=100)
```

### 数据清理

定期清理旧的审计日志数据：

```python
from datetime import datetime, timedelta

# 删除30天前的日志
cutoff_date = datetime.now() - timedelta(days=30)
db.query(AuditLog).filter(AuditLog.created_at < cutoff_date).delete()
db.commit()
```

## 合规性

### 数据保留

根据合规要求，审计日志应保留一定时间：
- 一般操作：保留90天
- 敏感操作：保留180天
- 管理操作：保留365天

### 数据保护

- 审计日志包含敏感信息，需要严格保护
- 只有授权用户才能访问审计日志
- 审计日志本身也需要审计

## 监控和告警

### 异常行为检测

监控以下异常行为：
- 频繁失败的操作
- 异常时间段的操作
- 异常IP地址的操作
- 敏感资源的频繁访问

### 告警规则

设置告警规则：
- 失败率超过10%
- 单用户操作频率过高
- 敏感操作失败

## 测试

运行审计日志测试：

```bash
pytest tests/test_audit_log_service.py -v
```

## 最佳实践

1. **合理配置审计范围**：只审计必要的操作，避免过度审计
2. **定期清理数据**：避免审计日志表过大影响性能
3. **监控审计日志**：及时发现异常行为
4. **保护审计数据**：确保审计日志的安全性和完整性
5. **合规性检查**：定期检查审计日志是否符合合规要求
