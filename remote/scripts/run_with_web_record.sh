#!/bin/bash
# ============================================================================
# run_with_web_record.sh — 启动摄像头识别 + 导览记录
# ============================================================================
# 用法：bash scripts/run_with_web_record.sh
#
# 说明：
#   启动摄像头实时识别，同时将每次讲解事件写入本地记录文件。
#   记录文件路径在 config/config.yaml → web.record_file 中配置。
#   本脚本不启动 HTTP API 服务（如需查询记录，请另开终端运行
#   bash scripts/run_web_api.sh）。
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  智能导览眼镜 — 摄像头识别 + 导览记录"
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

# 检查记录配置
RECORD_ENABLED=$(grep -A6 "^web:" config/config.yaml | grep "enable_record:" | awk '{print $2}')
RECORD_FILE=$(grep -A6 "^web:" config/config.yaml | grep "record_file:" | awk '{print $2}')

echo "[INFO] web.enable_record = ${RECORD_ENABLED:-true}"
echo "[INFO] Record file: ${RECORD_FILE:-data/guide_records.jsonl}"
echo ""

if [ "${RECORD_ENABLED:-true}" != "true" ]; then
    echo "[WARN] Record is disabled in config. To enable:"
    echo "  Edit config/config.yaml → web.enable_record: true"
    echo ""
fi

# 设置显示
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
if [ -f "/run/user/1000/gdm/Xauthority" ]; then
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
fi

echo "[INFO] Starting main.py with guide recording ..."
echo "[INFO] Press 'q' to quit."
echo ""

python3 main.py

echo ""
echo "[INFO] Session ended."
if [ -f "${RECORD_FILE:-data/guide_records.jsonl}" ]; then
    RECORD_COUNT=$(wc -l < "${RECORD_FILE:-data/guide_records.jsonl}")
    echo "[INFO] Total guide records: $RECORD_COUNT"
    echo "[INFO] View records: cat ${RECORD_FILE:-data/guide_records.jsonl}"
fi
