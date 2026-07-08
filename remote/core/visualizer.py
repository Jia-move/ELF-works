"""
core/visualizer.py — 可视化模块

负责检测框、类别标签、性能信息等画面叠加。

当前从 func.func_yolov8_optimize（检测框绘制）和
utils.perf_timer（性能叠层）重导出。
"""

import threading

import cv2

from func.func_yolov8_optimize import (  # noqa: F401
    draw,
    draw_box_corner,
    draw_label_type,
)

from utils.perf_timer import (  # noqa: F401
    draw_stats_on_frame,
)


# ============================================================================
# 展示信息状态存储（线程安全）
# ============================================================================

class _DisplayState:
    """存储最新一帧的检测信息、导览文本和系统状态。"""

    def __init__(self):
        self._lock = threading.Lock()

        # 检测信息
        self._detections = []        # [(class_name, confidence), ...]

        # 导览文本
        self._guide_text = ""        # 当前展示的导览/回答文本
        self._intro_text = ""        # 最新自动介绍文本

        # 当前识别对象
        self._current_object = ""    # 中文展示名，如 "故宫"
        self._current_object_raw = ""  # 模型原始名

        # 问答
        self._user_question = ""     # 最近用户问题
        self._last_answer = ""       # 最近系统回答

        # 状态
        self._qa_status = "idle"     # idle | intro | ready | answering
        self._cloud_mode = "mock"    # mock | deepseek | offline
        self._mode = "scenic"        # scenic | animal
        self._fps = 0.0
        self._last_update_time = ""  # 最近更新时间戳

        # 性能指标
        self._inference_ms = 0.0
        self._postprocess_ms = 0.0
        self._total_ms = 0.0

        # 记录状态
        self._record_status = "记录就绪"

    # ---- 批量更新（主线程调用）----

    def update_full(self, *,
                    detections: list = None,
                    guide_text: str = None,
                    intro_text: str = None,
                    current_object: str = None,
                    current_object_raw: str = None,
                    user_question: str = None,
                    last_answer: str = None,
                    qa_status: str = None,
                    cloud_mode: str = None,
                    fps: float = None,
                    mode: str = None,
                    record_status: str = None,
                    inference_ms: float = None,
                    postprocess_ms: float = None,
                    total_ms: float = None):
        """一次性更新所有字段（线程安全）。"""
        from datetime import datetime
        with self._lock:
            if detections is not None:
                self._detections = list(detections)
            if guide_text is not None:
                self._guide_text = guide_text
            if intro_text is not None:
                self._intro_text = intro_text
            if current_object is not None:
                self._current_object = current_object
            if current_object_raw is not None:
                self._current_object_raw = current_object_raw
            if user_question is not None:
                self._user_question = user_question
            if last_answer is not None:
                self._last_answer = last_answer
            if qa_status is not None:
                self._qa_status = qa_status
            if cloud_mode is not None:
                self._cloud_mode = cloud_mode
            if fps is not None:
                self._fps = fps
            if mode is not None:
                self._mode = mode
            if record_status is not None:
                self._record_status = record_status
            if inference_ms is not None:
                self._inference_ms = inference_ms
            if postprocess_ms is not None:
                self._postprocess_ms = postprocess_ms
            if total_ms is not None:
                self._total_ms = total_ms
            self._last_update_time = datetime.now().strftime("%H:%M:%S")

    # ---- 兼容旧接口 ----

    def update(self, detections: list, guide_text: str = ""):
        """兼容旧接口：仅更新检测和导览文本。"""
        self.update_full(detections=detections, guide_text=guide_text)

    # ---- 读取 ----

    def get(self):
        """兼容旧接口：返回 (detections, guide_text)。"""
        return self.get_detections(), self.get_guide_text()

    def get_all(self) -> dict:
        """获取全部状态（供 Qt 渲染）。"""
        with self._lock:
            return {
                "detections": list(self._detections),
                "guide_text": self._guide_text,
                "intro_text": self._intro_text,
                "current_object": self._current_object,
                "current_object_raw": self._current_object_raw,
                "user_question": self._user_question,
                "last_answer": self._last_answer,
                "qa_status": self._qa_status,
                "cloud_mode": self._cloud_mode,
                "mode": self._mode,
                "fps": self._fps,
                "last_update_time": self._last_update_time,
                "record_status": self._record_status,
                "inference_ms": self._inference_ms,
                "postprocess_ms": self._postprocess_ms,
                "total_ms": self._total_ms,
            }

    # ---- 单项读取 ----

    def get_detections(self) -> list:
        with self._lock:
            return list(self._detections)

    def get_guide_text(self) -> str:
        with self._lock:
            return self._guide_text

    def get_current_object(self) -> str:
        with self._lock:
            return self._current_object

    def get_qa_status(self) -> str:
        with self._lock:
            return self._qa_status

    def get_fps(self) -> float:
        with self._lock:
            return self._fps


_display_state = _DisplayState()


def get_display_state() -> _DisplayState:
    """获取全局展示信息状态单例。"""
    return _display_state


# ============================================================================
# 增强画面叠层
# ============================================================================

def draw_detection_overlay(frame, detections: list = None,
                           guide_text: str = None,
                           x: int = 10, y: int = 250):
    """在画面右侧绘制检测信息摘要 + 智能体讲解文本。

    使用英文/ASCII 字符（OpenCV 自带字体不支持中文）。
    中文信息请查看终端输出。

    Args:
        frame:      OpenCV BGR 图像（原地修改）
        detections: [(class_name, confidence), ...] 或 None
        guide_text: 智能体讲解摘要，或 None
        x, y:       起始位置
    """
    try:
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        line_height = 18
        color = (255, 255, 200)  # 淡黄色，区别于 FPS 绿色

        lines = []

        # 检测信息
        if detections:
            lines.append("--- Detections ---")
            for name, conf in detections[:5]:
                lines.append(f"  {name}  {conf:.2f}")
        else:
            lines.append("No detections")

        # 智能体讲解
        if guide_text:
            lines.append("--- Guide ---")
            # 英文模式下截断
            text = guide_text if len(guide_text) <= 55 else guide_text[:52] + "..."
            lines.append(f"  {text}")

        if not lines:
            return

        overlay = frame.copy()
        for i, line in enumerate(lines):
            y_pos = y + i * line_height
            (tw, th), baseline = cv2.getTextSize(line, font, font_scale, thickness)
            cv2.rectangle(
                overlay,
                (x - 4, y_pos - th - 4),
                (x + tw + 4, y_pos + baseline + 2),
                (0, 0, 0),
                -1,
            )
            cv2.putText(
                overlay, line, (x, y_pos),
                font, font_scale, color, thickness,
            )
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    except Exception:
        pass  # 叠层绝不阻塞主流程

