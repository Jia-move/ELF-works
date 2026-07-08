#!/usr/bin/env python3
"""
tests/test_dual_model_load.py — RK3588 双 RKNN 模型同时加载可行性评估

目的：
  - 验证 RK3588 能否同时加载 scenic 和 animal 两个 RKNN 模型
  - 评估 NPU、内存、线程池资源是否冲突
  - 本脚本为临时测试，不接入主程序，不修改任何现有文件

运行：
    cd /home/elf/Documents/sum
    DISPLAY=:0 python3 tests/test_dual_model_load.py

注意：
  - 使用较小线程数（每个模型 2 线程）避免资源过载
  - 不接入 UI / speaker / agent / 知识库
  - 仅做资源可行性验证，不作为正式架构方案
"""

import os
import sys
import time
import cv2
import numpy as np
import psutil
import threading

# ---------------------------------------------------------------------------
# 路径设置
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SCENIC_MODEL = os.path.join(PROJECT_ROOT, "rknnModel", "best.rknn")
ANIMAL_MODEL = "/home/elf/Documents/sum/rknnModel/best.rknn"
CAMERA_ID = "/dev/video21"

# 测试用线程数（较小值，避免过载）
SCENIC_THREADS = 2
ANIMAL_THREADS = 2

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _memory_mb() -> float:
    """获取当前进程 RSS 内存（MB）。"""
    try:
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def _npu_info():
    """读取 NPU 使用情况（RK3588 通过 debugfs）。"""
    paths = [
        "/sys/kernel/debug/rknpu/load",
        "/sys/class/devfreq/fdb90000.npu/load",
    ]
    for p in paths:
        try:
            with open(p, "r") as f:
                return f.read().strip()
        except Exception:
            continue
    return "N/A"


# ---------------------------------------------------------------------------
# 简化的单帧推理函数（不依赖全局 CLASSES，不绘制，不写 DetectionStore）
# ---------------------------------------------------------------------------

def _infer_one_frame(rknn_lite, frame_bgr, img_size=640):
    """对单帧执行 预处理→推理→后处理，返回 (boxes, classes, scores, elapsed_ms)。

    使用 letterbox + yolov8_post_process，跳过 draw/DetectionStore/perf。
    """
    from func.func_yolov8_optimize import letterbox, yolov8_post_process

    t0 = time.time()

    # 预处理（与 myFunc 完全一致）
    img = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    img, ratio, padding = letterbox(img, new_shape=(img_size, img_size))
    img = np.expand_dims(img, 0)

    # NPU 推理
    outputs = rknn_lite.inference(inputs=[img], data_format=['nhwc'])

    # 后处理
    boxes, classes, scores = yolov8_post_process(outputs)

    elapsed_ms = (time.time() - t0) * 1000
    return boxes, classes, scores, elapsed_ms


# ---------------------------------------------------------------------------
# 主测试流程
# ---------------------------------------------------------------------------

def test_dual_model():
    print("=" * 60)
    print("  RK3588 双 RKNN 模型同时加载可行性评估")
    print("=" * 60)
    print(f"  scenic model : {SCENIC_MODEL}")
    print(f"  animal model : {ANIMAL_MODEL}")
    print(f"  scenic threads: {SCENIC_THREADS}")
    print(f"  animal threads: {ANIMAL_THREADS}")
    print(f"  camera       : {CAMERA_ID}")
    print()

    # ---- 记录初始资源 ----
    mem_before = _memory_mb()
    print(f"[mem]  初始内存: {mem_before:.1f} MB")
    print(f"[npu]  初始 NPU:  {_npu_info()}")
    print()

    # =====================================================================
    # Phase 1: 加载 scenic 模型
    # =====================================================================
    print("--- Phase 1: 加载 scenic 模型 ---")
    t_scenic_load_start = time.time()

    try:
        from rknnpool.rknnpool_ld import rknnPoolExecutor
        from func.func_yolov8_optimize import myFunc as scenic_func
    except ImportError as e:
        print(f"[FATAL] 导入失败: {e}")
        return False

    # 确认 scenic 模型存在
    if not os.path.exists(SCENIC_MODEL):
        print(f"[FATAL] scenic 模型不存在: {SCENIC_MODEL}")
        return False

    scenic_pool = None
    try:
        scenic_pool = rknnPoolExecutor(
            rknnModel=SCENIC_MODEL,
            TPEs=SCENIC_THREADS,
            func=scenic_func,
        )
        t_scenic_load = (time.time() - t_scenic_load_start) * 1000
        mem_scenic = _memory_mb()
        print(f"  scenic 加载成功 ✓  (耗时: {t_scenic_load:.0f}ms, RSS: {mem_scenic:.1f} MB)")
    except Exception as e:
        print(f"  scenic 加载失败 ✗  ({e})")
        return False

    # =====================================================================
    # Phase 2: 在 scenic 已加载的基础上加载 animal 模型
    # =====================================================================
    print()
    print("--- Phase 2: 加载 animal 模型（scenic 仍驻留） ---")
    t_animal_load_start = time.time()

    if not os.path.exists(ANIMAL_MODEL):
        print(f"[FATAL] animal 模型不存在: {ANIMAL_MODEL}")
        scenic_pool.release()
        return False

    animal_pool = None
    try:
        animal_pool = rknnPoolExecutor(
            rknnModel=ANIMAL_MODEL,
            TPEs=ANIMAL_THREADS,
            func=scenic_func,  # 共用同一个回调（推理管线一致）
        )
        t_animal_load = (time.time() - t_animal_load_start) * 1000
        mem_dual = _memory_mb()
        print(f"  animal 加载成功 ✓  (耗时: {t_animal_load:.0f}ms, RSS: {mem_dual:.1f} MB)")
        print(f"  内存增量: {mem_dual - mem_scenic:.1f} MB")
        print(f"  总增量:   {mem_dual - mem_before:.1f} MB")
    except Exception as e:
        print(f"  animal 加载失败 ✗  ({e})")
        scenic_pool.release()
        return False

    # =====================================================================
    # Phase 3: 摄像头采集一帧
    # =====================================================================
    print()
    print("--- Phase 3: 摄像头采集测试帧 ---")

    cap = None
    test_frame = None
    try:
        cap = cv2.VideoCapture(CAMERA_ID)
        if not cap.isOpened():
            print(f"  [WARN] 摄像头打开失败: {CAMERA_ID}，使用随机噪声替代")
            test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        else:
            ret, frame = cap.read()
            if not ret:
                print(f"  [WARN] 摄像头读取失败，使用随机噪声替代")
                test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            else:
                test_frame = frame
                print(f"  摄像头帧: {frame.shape[1]}x{frame.shape[0]}")
    finally:
        if cap is not None:
            cap.release()

    mem_with_frame = _memory_mb()
    print(f"  RSS: {mem_with_frame:.1f} MB")
    print(f"  NPU:  {_npu_info()}")

    # =====================================================================
    # Phase 4: 分别对两个模型做推理（顺序，避免 CLASSES 竞争）
    # =====================================================================
    print()
    print("--- Phase 4: 推理测试 ---")

    from func.func_yolov8_optimize import set_classes

    # ---- 4a: scenic 推理 ----
    print()
    print("  4a. scenic 推理...")
    scenic_classes = (
        "The Forbidden City", "The Great Wall", "Terracotta Army",
        "Potala Palace", "Mogao Caves", "The Eiffel Tower",
        "The Sphinx", "The Leaning Tower of Pisa",
        "Sydney Opera House", "The Statue of Liberty",
        "Shanghai Oriental Pearl Tower",
    )
    set_classes(scenic_classes)

    # 用 scenic pool 的第一个 rknn_lite 实例做推理
    scenic_rknn = scenic_pool.rknnPool[0]
    scenic_results = None
    scenic_ms = -1.0
    try:
        boxes, classes, scores, scenic_ms = _infer_one_frame(
            scenic_rknn, test_frame
        )
        scenic_results = (boxes, classes, scores)
        if boxes is not None:
            names = [scenic_classes[int(c)] for c in classes[:5]]
            print(f"  scenic 推理成功 ✓  ({scenic_ms:.1f}ms)")
            print(f"  检测: {len(boxes)} 个目标: {names}")
        else:
            print(f"  scenic 推理成功 ✓  ({scenic_ms:.1f}ms, 无检测)")
    except Exception as e:
        print(f"  scenic 推理失败 ✗  ({e})")

    mem_after_scenic_infer = _memory_mb()

    # ---- 4b: animal 推理 ----
    print()
    print("  4b. animal 推理...")
    animal_classes = (
        "elephant", "monkey", "alpaca", "tiger", "panda",
        "lion", "fox", "camel", "raccoon", "bear",
    )
    set_classes(animal_classes)

    animal_rknn = animal_pool.rknnPool[0]
    animal_results = None
    animal_ms = -1.0
    try:
        boxes, classes, scores, animal_ms = _infer_one_frame(
            animal_rknn, test_frame
        )
        animal_results = (boxes, classes, scores)
        if boxes is not None:
            names = [animal_classes[int(c)] for c in classes[:5]]
            print(f"  animal 推理成功 ✓  ({animal_ms:.1f}ms)")
            print(f"  检测: {len(boxes)} 个目标: {names}")
        else:
            print(f"  animal 推理成功 ✓  ({animal_ms:.1f}ms, 无检测)")
    except Exception as e:
        print(f"  animal 推理失败 ✗  ({e})")

    mem_after_all_infer = _memory_mb()

    # ---- 4c: 连续 5 帧交错推理（轻度并发压力测试）----
    print()
    print("  4c. 交错推理压力测试 (各 5 帧)...")
    scenic_times = []
    animal_times = []
    for i in range(5):
        # scenic
        set_classes(scenic_classes)
        try:
            _, _, _, t = _infer_one_frame(scenic_rknn, test_frame)
            scenic_times.append(t)
        except Exception:
            scenic_times.append(-1)

        # animal
        set_classes(animal_classes)
        try:
            _, _, _, t = _infer_one_frame(animal_rknn, test_frame)
            animal_times.append(t)
        except Exception:
            animal_times.append(-1)

    valid_scenic = [t for t in scenic_times if t > 0]
    valid_animal = [t for t in animal_times if t > 0]
    if valid_scenic:
        print(f"  scenic: avg={np.mean(valid_scenic):.1f}ms  "
              f"min={np.min(valid_scenic):.1f}ms  max={np.max(valid_scenic):.1f}ms")
    if valid_animal:
        print(f"  animal: avg={np.mean(valid_animal):.1f}ms  "
              f"min={np.min(valid_animal):.1f}ms  max={np.max(valid_animal):.1f}ms")

    # =====================================================================
    # Phase 5: 资源汇总
    # =====================================================================
    print()
    print("--- Phase 5: 资源占用汇总 ---")
    mem_final = _memory_mb()
    print(f"  初始内存:        {mem_before:.1f} MB")
    print(f"  scenic 加载后:   {mem_scenic:.1f} MB  (+{mem_scenic - mem_before:.1f})")
    print(f"  双模型加载后:    {mem_dual:.1f} MB  (+{mem_dual - mem_before:.1f})")
    print(f"  推理后内存:      {mem_final:.1f} MB")
    print(f"  NPU 状态:        {_npu_info()}")

    # =====================================================================
    # Phase 6: 释放资源
    # =====================================================================
    print()
    print("--- Phase 6: 释放资源 ---")

    scenic_released = False
    animal_released = False

    if scenic_pool is not None:
        try:
            scenic_pool.release()
            scenic_released = True
            print("  scenic pool 释放成功 ✓")
        except Exception as e:
            print(f"  scenic pool 释放失败 ✗  ({e})")

    if animal_pool is not None:
        try:
            animal_pool.release()
            animal_released = True
            print("  animal pool 释放成功 ✓")
        except Exception as e:
            print(f"  animal pool 释放失败 ✗  ({e})")

    mem_after_release = _memory_mb()
    print(f"  释放后内存: {mem_after_release:.1f} MB")
    print()

    # =====================================================================
    # Phase 7: 结论
    # =====================================================================
    both_loaded = scenic_pool is not None and animal_pool is not None
    both_inferred = scenic_ms > 0 and animal_ms > 0
    both_released = scenic_released and animal_released

    print("=" * 60)
    print("  测试结论")
    print("=" * 60)
    print(f"  双模型加载: {'✓ 成功' if both_loaded else '✗ 失败'}")
    print(f"  双模型推理: {'✓ 成功' if both_inferred else '✗ 失败'}")
    print(f"  资源释放:   {'✓ 成功' if both_released else '✗ 部分失败'}")
    print(f"  总内存增量: {mem_dual - mem_before:.1f} MB")
    print()

    return both_loaded and both_inferred


# ===========================================================================
# 入口
# ===========================================================================
if __name__ == "__main__":
    rc = 0
    try:
        ok = test_dual_model()
        if not ok:
            rc = 1
    except KeyboardInterrupt:
        print("\n[exit] Interrupted")
        rc = 1
    except Exception as e:
        print(f"\n[FATAL] 未捕获异常: {e}")
        import traceback
        traceback.print_exc()
        rc = 1

    # 确保没有残留
    cv2.destroyAllWindows()
    sys.exit(rc)
