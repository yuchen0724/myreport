#!/bin/bash
# 测试模板页面返回逻辑

set -e

echo "========================================"
echo "  测试模板页面返回逻辑"
echo "========================================"
echo ""

PROJECT_ROOT="/home/zhou/myreport"
cd "$PROJECT_ROOT"

# 测试1: 检查TemplateVersion.vue的返回逻辑
echo "[测试1] 检查TemplateVersion.vue的返回逻辑..."
if grep -q "router.back()" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue使用router.back()返回"
else
    echo "✗ TemplateVersion.vue未使用router.back()返回"
    exit 1
fi

if grep -q "window.history.length > 1" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue检查历史记录"
else
    echo "✗ TemplateVersion.vue未检查历史记录"
    exit 1
fi

# 测试2: 检查TemplateDetail.vue的返回逻辑
echo ""
echo "[测试2] 检查TemplateDetail.vue的返回逻辑..."
if grep -q "router.back()" frontend/src/views/TemplateDetail.vue; then
    echo "✓ TemplateDetail.vue使用router.back()返回"
else
    echo "✗ TemplateDetail.vue未使用router.back()返回"
    exit 1
fi

if grep -q "window.history.length > 1" frontend/src/views/TemplateDetail.vue; then
    echo "✓ TemplateDetail.vue检查历史记录"
else
    echo "✗ TemplateDetail.vue未检查历史记录"
    exit 1
fi

# 测试3: 检查TemplateForm.vue的取消逻辑
echo ""
echo "[测试3] 检查TemplateForm.vue的取消逻辑..."
if grep -q "router.back()" frontend/src/views/TemplateForm.vue; then
    echo "✓ TemplateForm.vue使用router.back()取消"
else
    echo "✗ TemplateForm.vue未使用router.back()取消"
    exit 1
fi

if grep -q "window.history.length > 1" frontend/src/views/TemplateForm.vue; then
    echo "✓ TemplateForm.vue检查历史记录"
else
    echo "✗ TemplateForm.vue未检查历史记录"
    exit 1
fi

# 测试4: 检查调试日志
echo ""
echo "[测试4] 检查调试日志..."
if grep -q "console.log('返回上一页')" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue有调试日志"
else
    echo "✗ TemplateVersion.vue缺少调试日志"
    exit 1
fi

if grep -q "console.log('返回上一页')" frontend/src/views/TemplateDetail.vue; then
    echo "✓ TemplateDetail.vue有调试日志"
else
    echo "✗ TemplateDetail.vue缺少调试日志"
    exit 1
fi

if grep -q "console.log('取消编辑，返回上一页')" frontend/src/views/TemplateForm.vue; then
    echo "✓ TemplateForm.vue有调试日志"
else
    echo "✗ TemplateForm.vue缺少调试日志"
    exit 1
fi

# 测试5: 检查备用返回逻辑
echo ""
echo "[测试5] 检查备用返回逻辑..."
if grep -q "router.push('/templates')" frontend/src/views/TemplateVersion.vue; then
    echo "✓ TemplateVersion.vue有备用返回逻辑"
else
    echo "✗ TemplateVersion.vue缺少备用返回逻辑"
    exit 1
fi

if grep -q "router.push('/templates')" frontend/src/views/TemplateDetail.vue; then
    echo "✓ TemplateDetail.vue有备用返回逻辑"
else
    echo "✗ TemplateDetail.vue缺少备用返回逻辑"
    exit 1
fi

if grep -q "router.push('/templates')" frontend/src/views/TemplateForm.vue; then
    echo "✓ TemplateForm.vue有备用返回逻辑"
else
    echo "✗ TemplateForm.vue缺少备用返回逻辑"
    exit 1
fi

echo ""
echo "========================================"
echo "  所有测试通过！"
echo "========================================"
echo ""
echo "修复内容："
echo "1. ✓ TemplateVersion.vue使用router.back()返回上一页"
echo "2. ✓ TemplateDetail.vue使用router.back()返回上一页"
echo "3. ✓ TemplateForm.vue使用router.back()取消编辑"
echo "4. ✓ 所有页面都检查历史记录"
echo "5. ✓ 所有页面都有备用返回逻辑"
echo "6. ✓ 所有页面都有调试日志"
echo ""
echo "现在可以："
echo "- 从模板列表进入版本页面，返回时回到模板列表"
echo "- 从模板详情进入版本页面，返回时回到模板详情"
echo "- 从任何页面进入模板详情，返回时回到进入时的页面"
echo "- 取消编辑时返回到进入时的页面"
