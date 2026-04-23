#!/bin/bash
# 自定义报表查询系统一键启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/home/zhou/myreport"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# PID文件
REDIS_PID="$LOG_DIR/redis.pid"
CELERY_PID="$LOG_DIR/celery.pid"
BACKEND_PID="$LOG_DIR/backend.pid"
FRONTEND_PID="$LOG_DIR/frontend.pid"

# 端口配置
REDIS_PORT=6379
BACKEND_PORT=8000
FRONTEND_PORT=3000

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  自定义报表查询系统 - 一键启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查端口是否被占用
check_port() {
    local port=$1
    local service=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}警告: 端口 $port 已被占用 ($service)${NC}"
        return 1
    fi
    return 0
}

# 启动Redis
start_redis() {
    echo -e "${GREEN}[1/4] 启动 Redis 服务...${NC}"
    
    if check_port $REDIS_PORT "Redis"; then
        redis-server --daemonize yes --port $REDIS_PORT --logfile "$LOG_DIR/redis.log"
        sleep 2
        
        if redis-cli -p $REDIS_PORT ping >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Redis 启动成功 (端口: $REDIS_PORT)${NC}"
            echo $! > $REDIS_PID
        else
            echo -e "${RED}✗ Redis 启动失败${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}Redis 已在运行${NC}"
    fi
}

# 启动Celery Worker
start_celery() {
    echo -e "${GREEN}[2/4] 启动 Celery Worker...${NC}"
    
    cd $BACKEND_DIR
    export PYTHONPATH=$BACKEND_DIR:$PYTHONPATH
    
    # 检查是否已有celery进程
    if pgrep -f "celery.*worker" > /dev/null; then
        echo -e "${YELLOW}Celery Worker 已在运行${NC}"
    else
        nohup celery -A celery_config worker --loglevel=info --concurrency=4 -Q export \
            > "$LOG_DIR/celery.log" 2>&1 &
        echo $! > $CELERY_PID
        
        sleep 3
        
        if pgrep -f "celery.*worker" > /dev/null; then
            echo -e "${GREEN}✓ Celery Worker 启动成功${NC}"
        else
            echo -e "${RED}✗ Celery Worker 启动失败${NC}"
            tail -20 "$LOG_DIR/celery.log"
            return 1
        fi
    fi
}

# 启动后端服务
start_backend() {
    echo -e "${GREEN}[3/4] 启动后端服务...${NC}"
    
    if check_port $BACKEND_PORT "后端服务"; then
        cd $BACKEND_DIR
        nohup uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload \
            > "$LOG_DIR/backend.log" 2>&1 &
        echo $! > $BACKEND_PID
        
        sleep 5
        
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ 后端服务启动成功 (端口: $BACKEND_PORT)${NC}"
        else
            echo -e "${RED}✗ 后端服务启动失败${NC}"
            tail -20 "$LOG_DIR/backend.log"
            return 1
        fi
    else
        echo -e "${YELLOW}后端服务已在运行${NC}"
    fi
}

# 启动前端服务
start_frontend() {
    echo -e "${GREEN}[4/4] 启动前端服务...${NC}"
    
    if check_port $FRONTEND_PORT "前端服务"; then
        cd $FRONTEND_DIR
        nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
        echo $! > $FRONTEND_PID
        
        sleep 5
        
        if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
            echo -e "${GREEN}✓ 前端服务启动成功 (端口: $FRONTEND_PORT)${NC}"
        else
            echo -e "${RED}✗ 前端服务启动失败${NC}"
            tail -20 "$LOG_DIR/frontend.log"
            return 1
        fi
    else
        echo -e "${YELLOW}前端服务已在运行${NC}"
    fi
}

# 停止所有服务
stop_all() {
    echo -e "${YELLOW}停止所有服务...${NC}"
    
    # 停止前端
    if [ -f "$FRONTEND_PID" ]; then
        kill $(cat "$FRONTEND_PID") 2>/dev/null || true
        rm -f "$FRONTEND_PID"
    fi
    pkill -f "npm.*dev" || true
    
    # 停止后端
    if [ -f "$BACKEND_PID" ]; then
        kill $(cat "$BACKEND_PID") 2>/dev/null || true
        rm -f "$BACKEND_PID"
    fi
    pkill -f "uvicorn.*main:app" || true
    
    # 停止Celery
    if [ -f "$CELERY_PID" ]; then
        kill $(cat "$CELERY_PID") 2>/dev/null || true
        rm -f "$CELERY_PID"
    fi
    pkill -f "celery.*worker" || true
    
    # 停止Redis
    if [ -f "$REDIS_PID" ]; then
        kill $(cat "$REDIS_PID") 2>/dev/null || true
        rm -f "$REDIS_PID"
    fi
    redis-cli -p $REDIS_PORT shutdown 2>/dev/null || true
    
    echo -e "${GREEN}✓ 所有服务已停止${NC}"
}

# 查看服务状态
status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  服务状态${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    # Redis
    if redis-cli -p $REDIS_PORT ping >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis${NC} - 运行中 (端口: $REDIS_PORT)"
    else
        echo -e "${RED}✗ Redis${NC} - 未运行"
    fi
    
    # Celery
    if pgrep -f "celery.*worker" > /dev/null; then
        echo -e "${GREEN}✓ Celery Worker${NC} - 运行中"
    else
        echo -e "${RED}✗ Celery Worker${NC} - 未运行"
    fi
    
    # 后端
    if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端服务${NC} - 运行中 (端口: $BACKEND_PORT)"
    else
        echo -e "${RED}✗ 后端服务${NC} - 未运行"
    fi
    
    # 前端
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 前端服务${NC} - 运行中 (端口: $FRONTEND_PORT)"
    else
        echo -e "${RED}✗ 前端服务${NC} - 未运行"
    fi
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  访问地址${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "前端: ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
    echo -e "后端: ${GREEN}http://localhost:$BACKEND_PORT${NC}"
    echo -e "API文档: ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
}

# 查看日志
logs() {
    local service=$1
    
    case $service in
        redis)
            tail -f "$LOG_DIR/redis.log"
            ;;
        celery)
            tail -f "$LOG_DIR/celery.log"
            ;;
        backend)
            tail -f "$LOG_DIR/backend.log"
            ;;
        frontend)
            tail -f "$LOG_DIR/frontend.log"
            ;;
        *)
            echo "用法: $0 logs [redis|celery|backend|frontend]"
            ;;
    esac
}

# 主函数
main() {
    case "$1" in
        start)
            start_redis
            start_celery
            start_backend
            start_frontend
            echo ""
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}  所有服务启动完成！${NC}"
            echo -e "${GREEN}========================================${NC}"
            status
            ;;
        stop)
            stop_all
            ;;
        restart)
            stop_all
            sleep 2
            start_redis
            start_celery
            start_backend
            start_frontend
            status
            ;;
        status)
            status
            ;;
        logs)
            logs "$2"
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs [service]}"
            echo ""
            echo "命令:"
            echo "  start   - 启动所有服务"
            echo "  stop    - 停止所有服务"
            echo "  restart - 重启所有服务"
            echo "  status  - 查看服务状态"
            echo "  logs    - 查看日志 (redis|celery|backend|frontend)"
            echo ""
            echo "示例:"
            echo "  $0 start"
            echo "  $0 status"
            echo "  $0 logs backend"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
