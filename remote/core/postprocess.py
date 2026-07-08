"""
core/postprocess.py — YOLO 后处理模块

当前从 func.func_yolov8_optimize 重导出。
后续可将本机实现移入此模块，不影响调用方。
"""

from func.func_yolov8_optimize import (  # noqa: F401
    # 常量
    OBJ_THRESH,
    NMS_THRESH,
    IMG_SIZE,
    CLASSES,
    INTERESTED_CLASSES,
    CLASS_INDICES,
    INTERESTED_CLASS_INDICES,
    DRAW_BOXES,
    # 后处理函数
    filter_boxes,
    nms_boxes,
    dfl,
    box_process,
    yolov8_post_process,
    # 预处理
    letterbox,
    # 配置应用
    apply_detection_config,
)
from func.func_yolov8_optimize import set_classes as _func_set_classes


# ============================================================================
# set_classes 包装 — 解决 Python from-import 重导出引用不更新问题
# ============================================================================
# main.py 通过 `from core.postprocess import CLASSES` 导入 CLASSES，
# 若不在此同步更新 postprocess.CLASSES，set_classes() 只更新了
# func.func_yolov8_optimize 模块的 CLASSES，main.py 仍持有旧的 scenic 元组引用。
# ============================================================================

def set_classes(classes: tuple) -> None:
    """设置当前检测模式的类别表，并同步 postprocess 的 CLASSES 引用。

    Args:
        classes: 类别名元组，如 ("elephant", "monkey", ...)
    """
    global CLASSES
    _func_set_classes(classes)
    # 同步 postprocess 模块的 CLASSES，使所有 import 方能读取到更新后的值
    import func.func_yolov8_optimize as _f
    CLASSES = _f.CLASSES
