"""
core/result_formatter.py — 检测结果结构化模块

将 YOLO 原始输出（boxes/classes/scores）转换为 JSON 兼容的 dict，
供云端智能体消费。

使用方式：
    from core.result_formatter import (get_detection_store,
                                       format_detection,
                                       format_summary_text)

    store = get_detection_store()
    detections = store.get_latest()  # [(x1,y1,x2,y2), class_idx, score, img_w, img_h]
    result = format_detection(detections, frame_id, CLASSES)
    print(format_summary_text(result))
"""

import time
import threading
from datetime import datetime

from core.class_validator import is_valid_class_id, get_num_classes, warn_invalid_class


# ============================================================================
# 检测结果存储（线程安全）
# ============================================================================

class DetectionStore:
    """线程安全的检测结果存储。

    myFunc（worker 线程）写入原始检测结果，
    主线程读取并格式化为结构化数据。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._boxes = []
        self._classes = []
        self._scores = []
        self._img_width = 640
        self._img_height = 480

    def update(self, boxes, classes, scores, img_width, img_height):
        """更新最新一帧的检测结果。由 worker 线程调用。

        Args:
            boxes:   list of [x1, y1, x2, y2] (原始图像坐标，整数)
            classes: list of class indices (整数)
            scores:  list of confidence scores (浮点数)
            img_width:  原始图像宽度
            img_height: 原始图像高度
        """
        with self._lock:
            self._boxes = list(boxes) if boxes is not None else []
            self._classes = list(classes) if classes is not None else []
            self._scores = list(scores) if scores is not None else []
            self._img_width = img_width
            self._img_height = img_height

    def get_latest(self):
        """获取最新检测结果。由主线程调用。

        Returns:
            (boxes, classes, scores, img_width, img_height)
            其中 boxes/classes/scores 为平行列表。
            无检测时 boxes 为空列表。
        """
        with self._lock:
            return (
                list(self._boxes),
                list(self._classes),
                list(self._scores),
                self._img_width,
                self._img_height,
            )


# 全局单例
_detection_store = DetectionStore()


def get_detection_store() -> DetectionStore:
    """获取全局 DetectionStore 单例。"""
    return _detection_store


# ============================================================================
# 位置与大小判断
# ============================================================================

def _bbox_position(x1: int, y1: int, x2: int, y2: int,
                   img_w: int, img_h: int) -> str:
    """根据 bbox 中心点在图像中的水平位置和大小判断方位。

    Returns:
        "left" | "center" | "right" | "front-left" | "front-right"
    """
    cx = (x1 + x2) / 2 / img_w if img_w > 0 else 0.5

    if cx < 0.33:
        h_pos = "left"
    elif cx < 0.67:
        h_pos = "center"
    else:
        h_pos = "right"

    # 大面积目标视为"前方"
    area = (x2 - x1) * (y2 - y1)
    img_area = img_w * img_h
    ratio = area / img_area if img_area > 0 else 0

    if ratio > 0.15 and h_pos in ("left", "right"):
        return f"front-{h_pos}"
    return h_pos


def _bbox_size(x1: int, y1: int, x2: int, y2: int,
               img_w: int, img_h: int) -> str:
    """根据 bbox 面积占比判断目标大小。

    Returns:
        "small" | "medium" | "large"
    """
    area = (x2 - x1) * (y2 - y1)
    img_area = img_w * img_h
    ratio = area / img_area if img_area > 0 else 0

    if ratio < 0.05:
        return "small"
    elif ratio < 0.20:
        return "medium"
    else:
        return "large"


# ============================================================================
# 结构化输出
# ============================================================================

def format_detection(boxes, classes, scores, img_w, img_h,
                     frame_id: int = 0, class_names: tuple = (),
                     conf_threshold: float = 0.0) -> dict:
    """将原始检测结果转换为 JSON 兼容的结构化 dict。

    Args:
        boxes:     list of [x1, y1, x2, y2]
        classes:   list of class indices
        scores:    list of confidence scores
        img_w:     图像宽度
        img_h:     图像高度
        frame_id:  帧序号
        class_names: 类别名元组
        conf_threshold: 额外置信度过滤阈值

    Returns:
        dict 包含 timestamp, frame_id, objects, summary
    """
    objects = []
    class_counts = {}

    for box, cls_idx, score in zip(boxes, classes, scores):
        if score < conf_threshold:
            continue

        cls_idx_int = int(cls_idx)

        # 过滤越界类别（模型可能输出超出 class_names 范围的索引）
        if not is_valid_class_id(cls_idx_int):
            warn_invalid_class(class_id=cls_idx_int,
                               reason="class_id out of range, skipped in format_detection")
            continue

        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        cls_name = class_names[cls_idx_int]

        obj = {
            "class_name": cls_name,
            "confidence": round(float(score), 4),
            "bbox": [x1, y1, x2, y2],
            "position": _bbox_position(x1, y1, x2, y2, img_w, img_h),
            "size": _bbox_size(x1, y1, x2, y2, img_w, img_h),
        }
        objects.append(obj)
        class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

    # 按置信度降序排列
    objects.sort(key=lambda o: o["confidence"], reverse=True)

    # 主要目标类别（按出现次数降序，最多 5 个）
    main_objects = sorted(class_counts.keys(), key=lambda k: class_counts[k], reverse=True)[:5]

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "frame_id": frame_id,
        "objects": objects,
        "summary": {
            "object_count": len(objects),
            "main_objects": main_objects,
        },
    }


def format_summary_text(result: dict) -> str:
    """将结构化结果格式化为单行终端摘要字符串。"""
    if not result or not result.get("objects"):
        return "[detect] no objects"

    objs = result["objects"]
    top3 = objs[:3]
    parts = [f"[detect] {len(objs)} obj(s)"]
    for obj in top3:
        parts.append(
            f"{obj['class_name']}({obj['confidence']:.2f} {obj['position']})"
        )
    return " | ".join(parts)
