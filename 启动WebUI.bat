@echo off
chcp 65001 >nul
title 日本招聘爬虫 - Web UI

echo.
echo ================================================
echo     日本招聘爬虫系统 - Web UI 启动器
echo ================================================
echo.

cd /d "%~dp0"

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
echo [1/3] 检查依赖...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo        安装依赖中...
    pip install -r requirements.txt >nul 2>&1
    echo        依赖安装完成
)

REM 检查 Playwright 浏览器
echo [2/3] 检查 Playwright 浏览器...
python -c "from playwright.sync_api import sync_playwright" >nul 2>&1
if errorlevel 1 (
    echo        安装 Playwright 中...
    pip install playwright >nul 2>&1
    python -m playwright install chromium >nul 2>&1
    echo        Playwright 安装完成
)

REM 创建数据目录
if not exist "data" mkdir data
if not exist "data\output" mkdir data\output

echo [3/3] 启动 Web UI...
echo.
echo ================================================
echo     启动成功！打开浏览器访问:
echo     http://localhost:8080
echo.
echo     按 Ctrl+C 停止服务
echo ================================================
echo.

REM 启动 Web UI
python webui.py

pause
