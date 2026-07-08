"""
core/detector.py — RKNN YOLO 检测器模块

封装 RKNN 模型加载、推理线程池、以及完整的检测管线
（预处理 → NPU 推理 → 后处理 → 绘制）。

当前实现复用已有的 rknnpool 和 func_yolov8_optimize 模块，
后续可直接在本模块中替换为优化版本而不影响调用方。

使用方式：
    from core.detector import Detector

    det = Detector(config)
    det.put(frame)              # 提交帧（非阻塞）
    annotated_frame, ok = det.get()  # 获取结果（阻塞至有结果）
    det.release()
"""

from rknnpool.rknnpool_ld import rknnPoolExecutor
from func.func_yolov8_optimize import myFunc, apply_detection_config


class Detector:
    """RKNN YOLO 检测器。

    封装了：
    - 检测参数配置（阈值、输入尺寸等）
    - RKNN 模型加载（通过 rknnPoolExecutor）
    - 多线程异步推理
    - 预处理 / NPU 推理 / 后处理 / 绘制（通过 myFunc 回调）
    """

    def __init__(self, config: dict):
        """
        Args:
            config: load_config() 返回的完整配置字典
        """
        # 应用检测参数（conf_threshold, iou_threshold, IMG_SIZE 等）
        apply_detection_config(config)

        self._tpes = config["inference"]["thread_num"]
        self._pool = rknnPoolExecutor(
            rknnModel=config["model"]["path"],
            TPEs=self._tpes,
            func=myFunc,
        )

    @property
    def pool_size(self) -> int:
        """推理线程数。"""
        return self._tpes

    def put(self, frame):
        """提交一帧进行异步推理。非阻塞。

        Args:
            frame: BGR numpy array (H, W, 3)
        """
        self._pool.put(frame)

    def get(self):
        """获取一帧推理结果。阻塞至有结果可用。

        Returns:
            (annotated_frame, ok): annotated_frame 为 BGR numpy array，
                                   ok 为 bool（False 表示无结果）
        """
        return self._pool.get()

    def release(self):
        """释放 RKNN 资源和推理线程。"""
        if self._pool is not None:
            self._pool.release()
            self._pool = None

    def __del__(self):
        self.release()
