#!/bin/bash
# 测试一键启动脚本的功能

set -e

echo "========================================"
echo "  测试一键启动脚本"
echo "========================================"
echo ""

PROJECT_ROOT="/home/zhou/myreport"
cd "$PROJECT_ROOT"

# 测试1: 检查脚本是否存在
echo "[测试1] 检查启动脚本是否存在..."
if [ -f "start.sh" ]; then
    echo "✓ start.sh 存在"
else
    echo "✗ start.sh 不存在"
    exit 1
fi

if [ -f "start.bat" ]; then
    echo "✓ start.bat 存在"
else
    echo "✗ start.bat 不存在"
    exit 1
fi

# 测试2: 检查脚本权限
echo ""
echo "[测试2] 检查脚本权限..."
if [ -x "start.sh" ]; then
    echo "✓ start.sh 有执行权限"
else
    echo "✗ start.sh 没有执行权限"
    exit 1
fi

# 测试3: 测试status命令
echo ""
echo "[测试3] 测试status命令..."
./start.sh status > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ status命令执行成功"
else
    echo "✗ status命令执行失败"
    exit 1
fi

# 测试4: 检查日志目录
echo ""
echo "[测试4] 检查日志目录..."
if [ -d "logs" ]; then
    echo "✓ logs目录存在"
else
    echo "✗ logs目录不存在"
    exit 1
fi

# 测试5: 检查文档
echo ""
echo "[测试5] 检查文档..."
if [ -f "START_GUIDE.md" ]; then
    echo "✓ START_GUIDE.md 存在"
else
    echo "✗ START_GUIDE.md 不存在"
    exit 1
fi

# 测试6: 验证脚本语法
echo ""
echo "[测试6] 验证脚本语法..."
bash -n start.sh
if [ $? -eq 0 ]; then
    echo "✓ start.sh 语法正确"
else
    echo "✗ start.sh 语法错误"
    exit 1
fi

echo ""
echo "========================================"
echo "  所有测试通过！"
echo "========================================"
echo ""
echo "启动脚本已准备就绪，可以使用以下命令："
echo "  ./start.sh start    - 启动所有服务"
echo "  ./start.sh stop     - 停止所有服务"
echo "  ./start.sh status   - 查看服务状态"
echo "  ./start.sh logs     - 查看日志"
