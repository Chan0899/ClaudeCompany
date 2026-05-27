@echo off
chcp 65001 >nul
title 多Claude协同系统 Demo
cd /d "%~dp0"

echo ================================================
echo   多Claude协同系统 Demo
echo ================================================
echo.
echo  [1/2] 检查依赖...
pip install -r requirements.txt -q 2>nul

echo  [2/2] 启动服务...
echo.
echo ================================================
echo   打开浏览器访问: http://127.0.0.1:5000
echo   关闭此窗口即可停止服务
echo ================================================
echo.
start "" "http://127.0.0.1:5000"
python app.py
