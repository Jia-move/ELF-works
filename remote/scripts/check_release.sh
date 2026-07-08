#!/bin/bash
# ============================================================================
# check_release.sh — 正式版静态检查
# ============================================================================
# 用法：
#   bash scripts/check_release.sh
#
# 说明：
#   只做静态检查，不启动摄像头、不占用 NPU、不播放音频。
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  Smart Guide Glasses — Release Check"
echo "=========================================="

echo "[1/4] Required files"
test -f main.py
test -f config/config.yaml
test -f rknnModel/best.rknn
test -f data/class_map/classes_sum.json
test -f knowledge/sum_knowledge.json
echo "  ok"

echo "[2/4] Python syntax"
python3 -m py_compile \
    main.py \
    utils/config_loader.py \
    core/mode_manager.py \
    agent/deepseek_client.py \
    agent/qa_manager.py \
    agent/voice_handler.py \
    web/web_uploader.py
echo "  ok"

echo "[3/4] Configuration load"
python3 - <<'PY'
from utils.config_loader import load_config
from core.mode_manager import ModeManager

config = load_config("config/config.yaml")
mode = config.get("runtime", {}).get("mode", "sum")
manager = ModeManager(mode, config)
classes = manager.load_classes()

assert mode == "sum", f"runtime.mode should be sum, got {mode!r}"
assert manager.model_path.endswith("/home/elf/Documents/sum/rknnModel/best.rknn")
assert len(classes) == 21, f"sum class count should be 21, got {len(classes)}"

print(f"  mode={mode}")
print(f"  model={manager.model_path}")
print(f"  classes={len(classes)}")
PY

echo "[4/4] Runtime artifacts"
mkdir -p data
touch data/guide_records.jsonl data/guide_interactions.jsonl
echo "  ok"

echo "=========================================="
echo "  Release check passed"
echo "=========================================="

