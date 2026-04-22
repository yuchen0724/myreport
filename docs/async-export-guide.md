# 异步导出使用指南

## 功能介绍

异步导出功能支持大数据量的 Excel 和 PDF 导出，通过 Celery + Redis 实现任务队列管理。

## 使用方法

### 1. 创建导出任务

在异步导出页面（`/async-export`）：

1. 选择数据源
2. 输入 SQL 查询语句
3. 选择导出类型（Excel 或 PDF）
4. 点击"创建导出任务"按钮

### 2. 查看任务进度

- 任务列表会自动刷新（每 5 秒）
- 可以查看任务状态：等待中、处理中、已完成、失败
- 进度条显示任务完成百分比

### 3. 下载导出文件

- 任务完成后，"下载"按钮会变为可用状态
- 点击"下载"按钮即可下载导出文件
- 文件名格式：`export_{task_id}.xlsx` 或 `export_{task_id}.pdf`

### 4. 查看错误信息

- 如果任务失败，可以点击"查看错误"按钮
- 错误信息会显示具体的失败原因

## API 接口

### 创建导出任务
```http
POST /api/async-export/create
Content-Type: application/json

{
  "data_source_id": 1,
  "sql": "SELECT * FROM users LIMIT 10000",
  "export_type": "excel"
}
```

### 获取任务状态
```http
GET /api/async-export/task/{task_id}
```

### 获取用户任务列表
```http
GET /api/async-export/tasks?skip=0&limit=100
```

### 下载导出文件
```http
GET /api/async-export/download/{task_id}
```

## 注意事项

- 大数据量导出建议使用异步模式
- 任务会在后台处理，可以关闭页面
- 导出文件保留 7 天
- 每个用户最多同时运行 5 个导出任务
- 单次导出最多支持 100 万行数据

## 故障排查

### 任务一直处于"等待中"状态
- 检查 Celery Worker 是否正常运行
- 检查 Redis 连接是否正常

### 任务失败
- 查看错误信息，检查 SQL 语法
- 确认数据源连接配置正确
- 检查数据库权限

### 下载文件失败
- 确认任务已完成
- 检查文件是否已过期（超过 7 天）
- 检查导出目录权限
