#!/bin/bash
# 测试模板预览和版本页面功能

set -e

echo "========================================"
echo "  测试模板预览和版本页面功能"
echo "========================================"
echo ""

PROJECT_ROOT="/home/zhou/myreport"
cd "$PROJECT_ROOT"

# 测试1: 检查模板配置
echo "[测试1] 检查模板配置..."
TEMPLATE_CONFIG=$(curl --noproxy '*' -s http://localhost:8000/api/templates/1 | grep -o '"config":{[^}]*}')
echo "模板配置: $TEMPLATE_CONFIG"

if echo "$TEMPLATE_CONFIG" | grep -q "data_source_id"; then
    echo "✓ 模板配置包含data_source_id字段"
else
    echo "✗ 模板配置缺少data_source_id字段"
    exit 1
fi

if echo "$TEMPLATE_CONFIG" | grep -q "sql"; then
    echo "✓ 模板配置包含sql字段"
else
    echo "✗ 模板配置缺少sql字段"
    exit 1
fi

# 测试2: 检查数据源
echo ""
echo "[测试2] 检查数据源..."
DATASOURCES=$(curl --noproxy '*' -s http://localhost:8000/api/datasources)
DATASOURCE_COUNT=$(echo "$DATASOURCES" | grep -o '"id"' | wc -l)
echo "数据源数量: $DATASOURCE_COUNT"

if [ "$DATASOURCE_COUNT" -gt 0 ]; then
    echo "✓ 存在数据源"
    FIRST_DATASOURCE_ID=$(echo "$DATASOURCES" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
    echo "  第一个数据源ID: $FIRST_DATASOURCE_ID"
else
    echo "✗ 不存在数据源"
    exit 1
fi

# 测试3: 检查TemplateVersion.vue组件导入
echo ""
echo "[测试3] 检查TemplateVersion.vue组件导入..."
if grep -q "import Layout from '@/components/Layout.vue'" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue导入了Layout组件"
else
    echo "✗ TemplateVersion.vue未导入Layout组件"
    exit 1
fi

if grep -q "import Header from '@/components/Header.vue'" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue导入了Header组件"
else
    echo "✗ TemplateVersion.vue未导入Header组件"
    exit 1
fi

if grep -q "import Sidebar from '@/components/Sidebar.vue'" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue导入了Sidebar组件"
else
    echo "✗ TemplateVersion.vue未导入Sidebar组件"
    exit 1
fi

# 测试4: 检查TemplateVersionHistory.vue组件导入
echo ""
echo "[测试4] 检查TemplateVersionHistory.vue组件导入..."
if grep -q "import Layout from '@/components/Layout.vue'" frontend/src/views/TemplateVersionHistory.vue; then
    echo "✓ TemplateVersionHistory.vue导入了Layout组件"
else
    echo "✗ TemplateVersionHistory.vue未导入Layout组件"
    exit 1
fi

if grep -q "import Header from '@/components/Header.vue'" frontend/src/views/TemplateVersionHistory.vue; then
    echo "✓ TemplateVersionHistory.vue导入了Header组件"
else
    echo "✗ TemplateVersionHistory.vue未导入Header组件"
    exit 1
fi

if grep -q "import Sidebar from '@/components/Sidebar.vue'" frontend/src/views/TemplateVersionHistory.vue; then
    echo "✓ TemplateVersionHistory.vue导入了Sidebar组件"
else
    echo "✗ TemplateVersionHistory.vue未导入Sidebar组件"
    exit 1
fi

# 测试5: 检查query.js导出
echo ""
echo "[测试5] 检查query.js导出..."
if grep -q "export function executeQuery" frontend/src/api/query.js; then
    echo "✓ query.js导出了executeQuery函数"
else
    echo "✗ query.js未导出executeQuery函数"
    exit 1
fi

if grep -q "export function executeSQL" frontend/src/api/query.js; then
    echo "✓ query.js导出了executeSQL函数"
else
    echo "✗ query.js未导出executeSQL函数"
    exit 1
fi

echo ""
echo "========================================"
echo "  所有测试通过！"
echo "========================================"
echo ""
echo "修复内容："
echo "1. ✓ 模板配置已添加data_source_id字段"
echo "2. ✓ TemplateVersion.vue已添加Layout组件导入"
echo "3. ✓ query.js已添加executeQuery导出"
echo ""
echo "现在可以："
echo "- 正常预览模板查询结果"
echo "- 在版本页面看到导航栏"
echo "- 查看和编辑模板"
