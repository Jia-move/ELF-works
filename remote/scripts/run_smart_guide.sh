#!/bin/bash
# ============================================================================
# run_smart_guide.sh — 正式演示启动入口
# ============================================================================
# 用法：
#   bash scripts/run_smart_guide.sh
#
# 说明：
#   该脚本启动当前正式版 sum 合并识别链路：
#   摄像头 → RKNN/NPU YOLOv8 → 知识库/问答 → Qt 显示 → 语音播报 → Web 上传。
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  Smart Guide Glasses — Formal Runtime"
echo "  Project: $PROJECT_DIR"
echo "  Mode:    sum"
echo "=========================================="

if [ ! -f "main.py" ]; then
    echo "[ERROR] main.py not found in $PROJECT_DIR"
    exit 1
fi

if [ ! -f "rknnModel/best.rknn" ]; then
    echo "[ERROR] rknnModel/best.rknn not found"
    exit 1
fi

if [ -f "$HOME/.config/smart_guide/xfyun_env.sh" ]; then
    # shellcheck disable=SC1090
    source "$HOME/.config/smart_guide/xfyun_env.sh"
fi

if [ -f "$HOME/.config/smart_guide/deepseek_env.sh" ]; then
    # shellcheck disable=SC1090
    source "$HOME/.config/smart_guide/deepseek_env.sh"
fi

unset QT_QPA_PLATFORM_PLUGIN_PATH

if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
fi

echo "[INFO] DISPLAY=$DISPLAY"
echo "[INFO] XAUTHORITY=${XAUTHORITY:-not set}"
echo "[INFO] Starting formal runtime ..."
echo ""

python3 -u main.py --mode sum --ui qt

