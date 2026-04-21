#!/bin/bash

# 测试删除数据源功能

echo "=== 测试删除数据源功能 ==="

# 1. 获取 Token
echo "1. 获取 Token..."
TOKEN=$(curl --noproxy '*' -s http://localhost:8000/api/auth/login \
  -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ 获取 Token 失败"
  exit 1
fi

echo "✅ Token 获取成功"

# 2. 创建测试数据源
echo "2. 创建测试数据源..."
RESPONSE=$(curl --noproxy '*' -s -X POST http://localhost:8000/api/datasources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"测试删除数据源",
    "type":"POSTGRESQL",
    "host":"localhost",
    "port":5432,
    "database":"report_db",
    "username":"report_user",
    "password":"report_password"
  }')

DS_ID=$(echo $RESPONSE | grep -o '"id":[0-9]*' | cut -d':' -f2)

if [ -z "$DS_ID" ]; then
  echo "❌ 创建数据源失败"
  echo "响应: $RESPONSE"
  exit 1
fi

echo "✅ 数据源创建成功，ID: $DS_ID"

# 3. 获取数据源列表
echo "3. 获取数据源列表..."
curl --noproxy '*' -s http://localhost:8000/api/datasources \
  -H "Authorization: Bearer $TOKEN" | \
  grep -o '"id":[0-9]*' | cut -d':' -f2 | sort -n

echo "✅ 数据源列表获取成功"

# 4. 删除数据源
echo "4. 删除数据源 (ID: $DS_ID)..."
HTTP_STATUS=$(curl --noproxy '*' -s -X DELETE \
  http://localhost:8000/api/datasources/$DS_ID \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null \
  -w "%{http_code}")

if [ "$HTTP_STATUS" != "204" ]; then
  echo "❌ 删除数据源失败，HTTP 状态码: $HTTP_STATUS"
  exit 1
fi

echo "✅ 数据源删除成功"

# 5. 验证数据源已删除
echo "5. 验证数据源已删除..."
RESPONSE=$(curl --noproxy '*' -s http://localhost:8000/api/datasources \
  -H "Authorization: Bearer $TOKEN")

if echo $RESPONSE | grep -q "\"id\":$DS_ID"; then
  echo "❌ 数据源未删除"
  echo "响应: $RESPONSE"
  exit 1
fi

echo "✅ 数据源已成功删除"

# 6. 获取最终数据源列表
echo "6. 获取最终数据源列表..."
curl --noproxy '*' -s http://localhost:8000/api/datasources \
  -H "Authorization: Bearer $TOKEN" | \
  grep -o '"id":[0-9]*' | cut -d':' -f2 | sort -n

echo "✅ 测试完成！"
