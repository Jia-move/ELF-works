"""
core/async_pipeline.py — 三线程异步推理流水线

在现有 rknnPoolExecutor 基础上增加独立的摄像头线程和结果缓冲，
形成完整的三段式异步流水线：

    Camera Thread ──→ frame_queue ──→ Feeder Thread ──→ result_queue ──→ Main (Display)
                        (max N)       (rknnPool 复用)     (max M)        cv2.imshow

特性：
- 摄像头线程独立运行，持续采集最新帧
- Feeder 线程复用现有 rknnPoolExecutor 进行推理
- 队列有界，满时丢弃旧帧保留新帧（实时性优先）
- shutdown_event 控制线程安全退出
- 同步模式回退：不使用本模块即可回退到原有串行流程
"""

import queue
import threading

from core.detector import Detector


class AsyncPipeline:
    """三线程异步推理流水线。

    使用方式：
        pipeline = AsyncPipeline(camera, detector, config)
        pipeline.start()

        while running:
            result = pipeline.get_display_frame()
            if result is not None:
                last_frame = result
            # ... display last_frame ...
            # print(pipeline.queue_sizes)

        pipeline.stop()
    """

    def __init__(self, camera, detector: Detector, config: dict):
        """
        Args:
            camera: CameraCapture 实例
            detector: Detector 实例（内部封装 rknnPoolExecutor）
            config: 完整配置字典
        """
        self._camera = camera
        self._detector = detector

        # ---- 有界队列 ----
        pipe_cfg = config.get("pipeline", {})
        self._frame_queue = queue.Queue(
            maxsize=int(pipe_cfg.get("frame_queue_size", 4))
        )
        self._result_queue = queue.Queue(
            maxsize=int(pipe_cfg.get("result_queue_size", 2))
        )

        # ---- 线程控制 ----
        self._shutdown = threading.Event()
        self._camera_thread = threading.Thread(
            target=self._camera_loop, name="async-camera"
        )
        self._feeder_thread = threading.Thread(
            target=self._feeder_loop, name="async-feeder"
        )

    # ================================================================
    # 线程循环
    # ================================================================

    def _camera_loop(self):
        """摄像头线程：持续读取帧，队列满时丢弃最旧帧。"""
        while not self._shutdown.is_set():
            ret, frame = self._camera.read()
            if not ret:
                break
            try:
                self._frame_queue.put_nowait(frame)
            except queue.Full:
                # 丢弃最旧帧，放入最新帧（实时性优先）
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frame_queue.put_nowait(frame)
                except queue.Full:
                    pass  # 极端情况：同时被 feeder 取走，忽略

    def _feeder_loop(self):
        """喂料线程：从 frame_queue 取帧送入检测器，结果放入 result_queue。"""
        while not self._shutdown.is_set():
            # 取原始帧（带超时以便检查 shutdown）
            try:
                frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # 哨兵检查：stop() 会放入 None 唤醒线程
            if frame is None:
                continue

            # 提交推理（非阻塞）
            self._detector.put(frame)

            # 等待推理结果（阻塞，但 shutdown 时 get 仍会阻塞）
            # 注意：如果长期无结果（如 pipeline 未预填充），可能卡住
            # 解决方法：启动前预填充 detector
            try:
                result, ok = self._detector.get()
            except Exception:
                continue

            if not ok or result is None:
                continue

            # 放入结果队列
            try:
                self._result_queue.put_nowait(result)
            except queue.Full:
                try:
                    self._result_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._result_queue.put_nowait(result)
                except queue.Full:
                    pass

    # ================================================================
    # 生命周期
    # ================================================================

    def start(self):
        """启动流水线线程。"""
        self._shutdown.clear()
        self._camera_thread.start()
        self._feeder_thread.start()

    def stop(self, timeout: float = 3.0):
        """安全停止所有线程。

        Args:
            timeout: 等待每个线程退出的超时秒数
        """
        # 信号所有线程退出
        self._shutdown.set()

        # 给 feeder 线程一个唤醒信号（往 frame_queue 放哨兵）
        # 避免 feeder 卡在 frame_queue.get() 上
        try:
            self._frame_queue.put_nowait(None)
        except queue.Full:
            pass

        for t in (self._camera_thread, self._feeder_thread):
            if t.is_alive():
                t.join(timeout=timeout)

    # ================================================================
    # 显示接口
    # ================================================================

    def get_display_frame(self, timeout: float = 0.0):
        """获取最新推理结果（非阻塞）。

        Returns:
            annotated frame (numpy array) 或 None（无新结果）
        """
        try:
            return self._result_queue.get_nowait()
        except queue.Empty:
            return None

    # ================================================================
    # 状态查询
    # ================================================================

    @property
    def frame_queue_depth(self) -> int:
        """当前摄像头帧队列长度。"""
        return self._frame_queue.qsize()

    @property
    def result_queue_depth(self) -> int:
        """当前结果队列长度。"""
        return self._result_queue.qsize()

    @property
    def is_running(self) -> bool:
        """流水线是否正在运行。"""
        return not self._shutdown.is_set()
