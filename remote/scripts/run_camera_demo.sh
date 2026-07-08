#!/bin/bash
# ============================================================================
# run_camera_demo.sh — 智能导览眼镜摄像头演示启动脚本
# ============================================================================
# 用法：bash scripts/run_camera_demo.sh
# ============================================================================

set -e

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  智能导览眼镜 — 摄像头实时演示"
echo "  项目目录: $PROJECT_DIR"
echo "=========================================="

# 检查主程序是否存在
if [ ! -f "main.py" ]; then
    echo "[ERROR] main.py not found in $PROJECT_DIR"
    echo "  Please ensure you are in the correct project directory."
    exit 1
fi

# 检查模型文件是否存在
if [ ! -f "rknnModel/best.rknn" ]; then
    echo "[ERROR] rknnModel/best.rknn not found"
    echo "  The RKNN model file is required for NPU inference."
    exit 1
fi

# 设置显示环境
if [ -z "$DISPLAY" ]; then
    echo "[INFO] DISPLAY not set, using :0"
    export DISPLAY=:0
fi

# 设置 X 认证
if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
fi

echo "[INFO] Starting main.py ..."
echo "[INFO] Press 'q' in the display window to quit."
echo ""

# 运行主程序
python3 main.py

echo ""
echo "[INFO] Demo exited."
