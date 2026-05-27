#!/bin/bash
# 多Claude协同系统 Demo - 启动脚本 (Unix/Mac)

echo "================================================"
echo "  多Claude协同系统 Demo - 启动中..."
echo "================================================"
echo ""

cd "$(dirname "$0")"

echo "[1/2] 安装依赖..."
pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "依赖安装失败, 请检查Python环境"
    exit 1
fi

echo "[2/2] 启动服务..."
echo ""
python app.py
