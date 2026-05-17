#!/bin/bash
# 自定义报表查询系统一键启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录（自动检测）
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# PostgreSQL 版本
PG_VERSION=16
PG_CLUSTER="16 main"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# PID文件
PG_PID="$LOG_DIR/postgresql.pid"
REDIS_PID="$LOG_DIR/redis.pid"
CELERY_PID="$LOG_DIR/celery.pid"
BACKEND_PID="$LOG_DIR/backend.pid"
FRONTEND_PID="$LOG_DIR/frontend.pid"

# 端口配置
PG_PORT=5432
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

# 启动PostgreSQL
start_postgresql() {
    echo -e "${GREEN}[1/5] 启动 PostgreSQL 数据库...${NC}"

    if pg_isready -q -p $PG_PORT 2>/dev/null; then
        echo -e "${YELLOW}PostgreSQL 已在运行 (端口: $PG_PORT)${NC}"
        return 0
    fi

    # 检查是否有 stale pid 文件
    PG_PIDFILE="/var/lib/postgresql/$PG_VERSION/main/postmaster.pid"
    if [ -f "$PG_PIDFILE" ] && ! pg_isready -q -p $PG_PORT 2>/dev/null; then
        sudo pg_ctlcluster $PG_VERSION main start 2>&1
    else
        sudo pg_ctlcluster $PG_VERSION main start 2>&1
    fi

    sleep 2

    if pg_isready -q -p $PG_PORT; then
        echo -e "${GREEN}✓ PostgreSQL 启动成功 (端口: $PG_PORT)${NC}"
    else
        echo -e "${RED}✗ PostgreSQL 启动失败${NC}"
        sudo pg_ctlcluster $PG_VERSION main status 2>&1 || true
        return 1
    fi
}

# 启动Redis
start_redis() {
    echo -e "${GREEN}[2/5] 启动 Redis 服务...${NC}"
    
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
    echo -e "${GREEN}[3/5] 启动 Celery Worker...${NC}"
    
    cd $BACKEND_DIR
    export PYTHONPATH=$BACKEND_DIR:$PYTHONPATH
    
    # 使用 venv 中的 celery（确保 lightgbm 等依赖可用）
    CELERY_BIN="$BACKEND_DIR/.venv/bin/celery"
    if [ ! -f "$CELERY_BIN" ]; then
        CELERY_BIN="celery"
    fi
    
    # 检查是否已有celery进程
    if pgrep -f "celery.*worker" > /dev/null; then
        echo -e "${YELLOW}Celery Worker 已在运行${NC}"
    else
        echo -e "${GREEN}启动 Celery Worker (含 Beat 调度器)...${NC}"
        nohup $CELERY_BIN -A celery_config worker --loglevel=info --concurrency=2 -Q export,celery -B \
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
    echo -e "${GREEN}[4/5] 启动后端服务...${NC}"
    
    if check_port $BACKEND_PORT "后端服务"; then
        cd $BACKEND_DIR
        
        # 使用 venv 中的 uvicorn
        UVICORN_BIN="$BACKEND_DIR/.venv/bin/uvicorn"
        if [ ! -f "$UVICORN_BIN" ]; then
            UVICORN_BIN="uvicorn"
        fi
        
        nohup env PYTHONPATH="$BACKEND_DIR:$HOME/.local/lib/python3.12/site-packages:$PYTHONPATH" $UVICORN_BIN app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload \
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
    echo -e "${GREEN}[5/5] 启动前端服务...${NC}"
    
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
    
    # ===== 强制停止占用端口的进程 =====
    
    # 前端 - 强制杀掉占用 3000 端口的进程
    echo -e "${YELLOW}停止前端服务 (端口: $FRONTEND_PORT)...${NC}"
    fuser -k $FRONTEND_PORT/tcp 2>/dev/null || true
    pkill -f "vite.*$FRONTEND_PORT" || true
    pkill -f "npm.*dev" || true
    pkill -f "node.*vite" || true
    
    # 后端 - 强制杀掉占用 8000 端口的进程
    echo -e "${YELLOW}停止后端服务 (端口: $BACKEND_PORT)...${NC}"
    fuser -k $BACKEND_PORT/tcp 2>/dev/null || true
    pkill -f "uvicorn.*main:app" || true
    pkill -f "python.*uvicorn" || true
    
    # Celery
    echo -e "${YELLOW}停止 Celery Worker...${NC}"
    pkill -f "celery.*worker" || true
    pkill -9 -f "celery" || true
    
    # Redis
    echo -e "${YELLOW}停止 Redis 服务...${NC}"
    redis-cli -p $REDIS_PORT shutdown 2>/dev/null || true
    fuser -k $REDIS_PORT/tcp 2>/dev/null || true
    
    # PostgreSQL
    if pg_isready -q -p $PG_PORT 2>/dev/null; then
        echo -e "${YELLOW}停止 PostgreSQL...${NC}"
        sudo pg_ctlcluster $PG_VERSION main stop 2>/dev/null || true
        for i in {1..10}; do
            if ! pg_isready -q -p $PG_PORT 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if pg_isready -q -p $PG_PORT 2>/dev/null; then
            echo -e "${RED}✗ PostgreSQL 停止超时，强制终止...${NC}"
            sudo pg_ctlcluster $PG_VERSION main stop -m fast 2>/dev/null || true
            sleep 2
        fi
    fi
    
    # ===== 等待端口释放 =====
    sleep 2
    
    # 验证端口已释放
    for port in $FRONTEND_PORT $BACKEND_PORT $REDIS_PORT; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo -e "${RED}警告: 端口 $port 仍未释放，强制杀掉...${NC}"
            fuser -k -9 $port/tcp 2>/dev/null || true
        fi
    done
    
    # 清理 PID 文件
    rm -f "$FRONTEND_PID" "$BACKEND_PID" "$CELERY_PID" "$REDIS_PID"
    
    sleep 1
    echo -e "${GREEN}✓ 所有服务已停止${NC}"
}

# 查看服务状态
status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  服务状态${NC}"
    echo -e "${BLUE}========================================${NC}"

    # PostgreSQL
    if pg_isready -q -p $PG_PORT 2>/dev/null; then
        echo -e "${GREEN}✓ PostgreSQL${NC} - 运行中 (端口: $PG_PORT)"
    else
        echo -e "${RED}✗ PostgreSQL${NC} - 未运行"
    fi

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
        postgresql|pg)
            journalctl -u postgresql@$PG_VERSION-main -f --no-pager 2>/dev/null || \
            sudo tail -f /var/log/postgresql/postgresql-$PG_VERSION-main.log
            ;;
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
            echo "用法: $0 logs [postgresql|redis|celery|backend|frontend]"
            ;;
    esac
}

# 主函数
main() {
    case "$1" in
        start)
            start_postgresql
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
            start_postgresql
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
            echo "  logs    - 查看日志 (postgresql|redis|celery|backend|frontend)"
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
