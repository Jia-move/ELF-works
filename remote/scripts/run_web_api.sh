#!/bin/bash
# ============================================================================
# run_web_api.sh — 启动导览记录 HTTP API 服务
# ============================================================================
# 用法：bash scripts/run_web_api.sh
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  导览记录 Web API 服务"
echo "  项目目录: $PROJECT_DIR"
echo "=========================================="

# 检查必要文件
if [ ! -f "web/simple_api_server.py" ]; then
    echo "[ERROR] web/simple_api_server.py not found"
    exit 1
fi

# 读取配置中的端口（简单 grep，不依赖 yaml 库）
PORT=$(grep -A5 "^web:" config/config.yaml | grep "port:" | awk '{print $2}')
PORT=${PORT:-8080}

echo "[INFO] Starting API server on port $PORT ..."
echo ""
echo "  接口地址："
echo "    http://localhost:$PORT/api/guide/records"
echo "    http://localhost:$PORT/api/guide/status"
echo ""
echo "  示例："
echo "    curl http://localhost:$PORT/api/guide/records"
echo "    curl http://localhost:$PORT/api/guide/status"
echo ""

python3 web/simple_api_server.py

echo ""
echo "[INFO] API server exited."
