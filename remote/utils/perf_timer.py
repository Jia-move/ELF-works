"""
perf_timer.py — 轻量级性能统计模块

用于 RK3588 智能导览眼镜项目的推理性能测量。
线程安全：支持多线程 worker 同时记录，主线程读取汇总。

使用方式：
    from utils.perf_timer import get_stats, draw_stats_on_frame

    # 在推理回调中
    stats = get_stats()
    t0 = time.time()
    # ... do work ...
    stats.record_worker(inference_ms=(time.time()-t0)*1000)

    # 在主循环中
    stats.record_frame(capture_ms=..., display_ms=..., frame_period_ms=...)

    # 终端打印
    summary = stats.get_summary()
    print(format_summary(summary))

    # 画面叠加
    draw_stats_on_frame(frame, summary)
"""

import time
import threading
from collections import deque

import cv2


class PerfStats:
    """线程安全的滚动窗口性能统计收集器。

    两个独立的记录通道：
    - record_worker(): 推理工作线程调用（myFunc 内部各阶段耗时）
    - record_frame():  主线程调用（采集、显示、帧周期）
    """

    def __init__(self, window_size: int = 30):
        self._lock = threading.Lock()
        self._worker_records = deque(maxlen=window_size)
        self._frame_records = deque(maxlen=window_size)
        self._total_frames = 0
        self._start_time = time.time()

    # ---- 写入接口（线程安全）----

    def record_worker(self, **kwargs):
        """记录一帧推理管线的各阶段耗时。由 worker 线程调用。"""
        with self._lock:
            self._worker_records.append(kwargs)

    def record_frame(self, **kwargs):
        """记录主线程的帧周期耗时。由主线程调用。"""
        with self._lock:
            self._frame_records.append(kwargs)
            self._total_frames += 1

    # ---- 读取接口 ----

    def get_summary(self) -> dict:
        """获取滚动窗口内的平均统计值。

        Returns:
            dict 包含:
                total_frames: 已处理总帧数
                elapsed_s: 程序运行总秒数
                fps_instant: 瞬时 FPS（基于最近一帧）
                worker: {preprocess_ms, inference_ms, postprocess_ms, draw_ms, worker_total_ms}
                frame:  {capture_ms, display_ms, frame_period_ms}
        """
        with self._lock:
            result = {
                'total_frames': self._total_frames,
                'elapsed_s': time.time() - self._start_time,
            }

            # 瞬时 FPS（基于最近一帧的帧周期）
            if self._frame_records:
                last = self._frame_records[-1]
                period = last.get('frame_period_ms', 0)
                result['fps_instant'] = 1000.0 / period if period > 0 else 0

            # Worker 平均耗时
            if self._worker_records:
                n = len(self._worker_records)
                avg = {}
                for rec in self._worker_records:
                    for k, v in rec.items():
                        avg[k] = avg.get(k, 0) + v / n
                result['worker'] = avg

            # Frame 平均耗时
            if self._frame_records:
                n = len(self._frame_records)
                avg = {}
                for rec in self._frame_records:
                    for k, v in rec.items():
                        avg[k] = avg.get(k, 0) + v / n
                result['frame'] = avg

            # 30 帧平均 FPS
            if self._frame_records and 'frame_period_ms' in result.get('frame', {}):
                avg_period = result['frame']['frame_period_ms']
                result['fps_avg_30'] = 1000.0 / avg_period if avg_period > 0 else 0
            else:
                result['fps_avg_30'] = 0

            return result

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def elapsed(self) -> float:
        return time.time() - self._start_time


# ---- 全局单例 ----

_global_stats = PerfStats(window_size=30)


def get_stats() -> PerfStats:
    """获取全局 PerfStats 单例。"""
    return _global_stats


# ---- 格式化输出 ----

def format_summary(stats: dict) -> str:
    """将统计摘要格式化为单行终端输出字符串。"""
    if not stats:
        return "[perf] waiting for data..."

    total = stats.get('total_frames', 0)
    fps_inst = stats.get('fps_instant', 0)
    fps_avg = stats.get('fps_avg_30', 0)
    worker = stats.get('worker', {})
    frame_m = stats.get('frame', {})

    parts = [
        f"FPS:{fps_inst:5.1f}",
        f"avg30:{fps_avg:5.1f}",
        f"frames:{total}",
    ]

    # Worker 管线耗时
    if worker:
        parts.append(
            f"infer:{worker.get('inference_ms', 0):.0f}ms"
        )
        parts.append(
            f"pre:{worker.get('preprocess_ms', 0):.1f}ms"
        )
        parts.append(
            f"post:{worker.get('postprocess_ms', 0):.1f}ms"
        )
        parts.append(
            f"draw:{worker.get('draw_ms', 0):.1f}ms"
        )

    # 主线程耗时
    if frame_m:
        parts.append(
            f"cap:{frame_m.get('capture_ms', 0):.1f}ms"
        )
        parts.append(
            f"get:{frame_m.get('pool_get_ms', 0):.1f}ms"
        )
        parts.append(
            f"disp:{frame_m.get('display_ms', 0):.1f}ms"
        )
        parts.append(
            f"total:{frame_m.get('frame_period_ms', 0):.0f}ms"
        )

    return " | ".join(parts)


# ---- 画面叠加 ----

def draw_stats_on_frame(frame, stats: dict, x: int = 10, y: int = 30):
    """在画面上叠加性能信息。线程安全，绝不抛异常。

    Args:
        frame: OpenCV BGR 图像（原地修改）
        stats: get_summary() 返回的统计字典
        x, y: 左上角起始位置
    """
    try:
        worker = stats.get('worker', {})
        frame_m = stats.get('frame', {})

        lines = [
            f"FPS: {stats.get('fps_instant', 0):.1f}  (30avg: {stats.get('fps_avg_30', 0):.1f})",
            f"Total: {frame_m.get('frame_period_ms', 0):.0f}ms  "
            f"Infer: {worker.get('inference_ms', 0):.0f}ms",
            f"Pre: {worker.get('preprocess_ms', 0):.1f}ms  "
            f"Post: {worker.get('postprocess_ms', 0):.1f}ms  "
            f"Draw: {worker.get('draw_ms', 0):.1f}ms",
            f"Cap: {frame_m.get('capture_ms', 0):.1f}ms  "
            f"Disp: {frame_m.get('display_ms', 0):.1f}ms  "
            f"Get: {frame_m.get('pool_get_ms', 0):.1f}ms",
        ]

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        line_height = 18

        # ---- 只复制一次全帧，所有背景和文字画在 overlay 上，最后一次性 blend ----
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
                font, font_scale, (0, 255, 0), thickness,
            )
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    except Exception:
        pass  # 统计信息绝不影响主流程
