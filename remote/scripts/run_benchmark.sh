#!/bin/bash
# ============================================================================
# run_benchmark.sh — 性能测试启动脚本
# ============================================================================
# 用法：bash scripts/run_benchmark.sh
#
# 说明：
#   启动摄像头实时识别，在终端观察 FPS、推理耗时、队列状态。
#   不训练模型、不转换模型、不修改配置。
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  智能导览眼镜 — 性能基准测试"
echo "  项目目录: $PROJECT_DIR"
echo "=========================================="

# 检查必要文件
if [ ! -f "main.py" ]; then
    echo "[ERROR] main.py not found"
    exit 1
fi
if [ ! -f "rknnModel/best.rknn" ]; then
    echo "[ERROR] rknnModel/best.rknn not found"
    exit 1
fi

# 设置显示
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
fi

echo ""
echo "  性能指标说明："
echo "    FPS / avg30      — 瞬时帧率 / 30帧平均"
echo "    infer            — NPU 推理耗时 (ms)"
echo "    pre/post/draw    — 预处理/后处理/绘制耗时 (ms)"
echo "    cap/disp/get     — 采集/显示/队列获取耗时 (ms)"
echo "    total            — 单帧总耗时 (ms)"
echo "    fq / rq          — 帧队列/结果队列深度 (async 模式)"
echo ""
echo "  建议："
echo "    - 同步模式 (pipeline.async_mode=false): 关注 FPS + infer + total"
echo "    - 异步模式 (pipeline.async_mode=true):  额外关注 fq/rq 队列深度"
echo "    - 按 'q' 退出后查看退出摘要"
echo ""

echo "[INFO] Starting main.py ..."
echo ""

python3 main.py

echo ""
echo "[INFO] Benchmark session ended."
echo "[INFO] 退出时已打印性能统计摘要（含总帧数/总时长/平均FPS/分项耗时）。"
