@echo off
REM 自定义报表查询系统一键启动脚本 (Windows版本)

setlocal enabledelayedexpansion

REM 颜色定义
set RED=[91m
set GREEN=[92m
set YELLOW=[93m
set BLUE=[94m
set NC=[0m

REM 项目根目录
set PROJECT_ROOT=%~dp0
set BACKEND_DIR=%PROJECT_ROOT%backend
set FRONTEND_DIR=%PROJECT_ROOT%frontend

REM 日志目录
set LOG_DIR=%PROJECT_ROOT%logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 端口配置
set REDIS_PORT=6379
set BACKEND_PORT=8000
set FRONTEND_PORT=3000

echo %BLUE%========================================%NC%
echo %BLUE%  自定义报表查询系统 - 一键启动脚本%NC%
echo %BLUE%========================================%NC%
echo.

if "%1"=="" goto usage
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="status" goto status
if "%1"=="logs" goto logs
goto usage

:start
echo %GREEN%[1/4] 启动 Redis 服务...%NC%

REM 检查Redis是否已运行
netstat -ano | findstr ":%REDIS_PORT%" >nul
if %errorlevel% equ 0 (
    echo %YELLOW%Redis 已在运行%NC%
) else (
    start /B redis-server --port %REDIS_PORT% --logfile "%LOG_DIR%\redis.log"
    timeout /t 2 /nobreak >nul
    echo %GREEN%✓ Redis 启动成功 (端口: %REDIS_PORT%)%NC%
)

echo %GREEN%[2/4] 启动 Celery Worker...%NC%
cd /d "%BACKEND_DIR%"
set PYTHONPATH=%BACKEND_DIR%;%PYTHONPATH%

REM 检查Celery是否已运行
tasklist | findstr "python.exe" >nul
if %errorlevel% equ 0 (
    echo %YELLOW%Celery Worker 可能已在运行%NC%
) else (
    start /B celery -A celery_config worker --loglevel=info --concurrency=4 -Q export > "%LOG_DIR%\celery.log" 2>&1
    timeout /t 3 /nobreak >nul
    echo %GREEN%✓ Celery Worker 启动成功%NC%
)

echo %GREEN%[3/4] 启动后端服务...%NC%

REM 检查后端是否已运行
netstat -ano | findstr ":%BACKEND_PORT%" >nul
if %errorlevel% equ 0 (
    echo %YELLOW%后端服务已在运行%NC%
) else (
    start /B uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload > "%LOG_DIR%\backend.log" 2>&1
    timeout /t 5 /nobreak >nul
    echo %GREEN%✓ 后端服务启动成功 (端口: %BACKEND_PORT%)%NC%
)

echo %GREEN%[4/4] 启动前端服务...%NC%
cd /d "%FRONTEND_DIR%"

REM 检查前端是否已运行
netstat -ano | findstr ":%FRONTEND_PORT%" >nul
if %errorlevel% equ 0 (
    echo %YELLOW%前端服务已在运行%NC%
) else (
    start /B npm run dev > "%LOG_DIR%\frontend.log" 2>&1
    timeout /t 5 /nobreak >nul
    echo %GREEN%✓ 前端服务启动成功 (端口: %FRONTEND_PORT%)%NC%
)

echo.
echo %GREEN%========================================%NC%
echo %GREEN%  所有服务启动完成！%NC%
echo %GREEN%========================================%NC%
goto status

:stop
echo %YELLOW%停止所有服务...%NC%

REM 停止前端
taskkill /F /IM node.exe >nul 2>&1

REM 停止后端
taskkill /F /IM python.exe >nul 2>&1

REM 停止Redis
taskkill /F /IM redis-server.exe >nul 2>&1

echo %GREEN%✓ 所有服务已停止%NC%
goto :eof

:restart
call :stop
timeout /t 2 /nobreak >nul
call :start
goto :eof

:status
echo %BLUE%========================================%NC%
echo %BLUE%  服务状态%NC%
echo %BLUE%========================================%NC%

REM Redis
netstat -ano | findstr ":%REDIS_PORT%" >nul
if %errorlevel% equ 0 (
    echo %GREEN%✓ Redis%NC% - 运行中 (端口: %REDIS_PORT%)
) else (
    echo %RED%✗ Redis%NC% - 未运行
)

REM Celery
tasklist | findstr "python.exe" >nul
if %errorlevel% equ 0 (
    echo %GREEN%✓ Celery Worker%NC% - 运行中
) else (
    echo %RED%✗ Celery Worker%NC% - 未运行
)

REM 后端
netstat -ano | findstr ":%BACKEND_PORT%" >nul
if %errorlevel% equ 0 (
    echo %GREEN%✓ 后端服务%NC% - 运行中 (端口: %BACKEND_PORT%)
) else (
    echo %RED%✗ 后端服务%NC% - 未运行
)

REM 前端
netstat -ano | findstr ":%FRONTEND_PORT%" >nul
if %errorlevel% equ 0 (
    echo %GREEN%✓ 前端服务%NC% - 运行中 (端口: %FRONTEND_PORT%)
) else (
    echo %RED%✗ 前端服务%NC% - 未运行
)

echo.
echo %BLUE%========================================%NC%
echo %BLUE%  访问地址%NC%
echo %BLUE%========================================%NC%
echo 前端: %GREEN%http://localhost:%FRONTEND_PORT%%NC%
echo 后端: %GREEN%http://localhost:%BACKEND_PORT%%NC%
echo API文档: %GREEN%http://localhost:%BACKEND_PORT%/docs%NC%
goto :eof

:logs
if "%2"=="" (
    echo 用法: %0 logs [redis^|celery^|backend^|frontend]
    goto :eof
)
if "%2"=="redis" (
    type "%LOG_DIR%\redis.log"
    goto :eof
)
if "%2"=="celery" (
    type "%LOG_DIR%\celery.log"
    goto :eof
)
if "%2"=="backend" (
    type "%LOG_DIR%\backend.log"
    goto :eof
)
if "%2"=="frontend" (
    type "%LOG_DIR%\frontend.log"
    goto :eof
)
echo 无效的服务名称: %2
goto :eof

:usage
echo 用法: %0 {start^|stop^|restart^|status^|logs [service]}
echo.
echo 命令:
echo   start   - 启动所有服务
echo   stop    - 停止所有服务
echo   restart - 重启所有服务
echo   status  - 查看服务状态
echo   logs    - 查看日志 (redis^|celery^|backend^|frontend)
echo.
echo 示例:
echo   %0 start
echo   %0 status
echo   %0 logs backend
exit /b 1
