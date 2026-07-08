"""
ui/display_manager.py — 显示模式管理器

统一 OpenCV / Qt 显示后端。main.py 通过本模块做所有显示操作，
不直接调用 cv2.imshow / cv2.namedWindow / cv2.waitKey。

使用方式：
    from ui.display_manager import DisplayManager
    dm = DisplayManager(config)
    dm.setup_window("title", 1420, 800)
    while True:
        frame = dm.resize_frame(raw_frame, 1420, 800)
        dm.show_frame(frame)
        key = dm.get_key()
        if dm.should_quit(key):
            break
    dm.cleanup()
"""

import cv2
from ui.qt_viewer import create_viewer, is_qt_available, get_qt_backend, process_qt_events


class DisplayManager:
    """显示模式管理器 — 统一 OpenCV / Qt 后端。"""

    def __init__(self, config: dict):
        ui_cfg = config.get("ui", {})
        self._mode = ui_cfg.get("mode", "opencv")
        self._fallback_enabled = ui_cfg.get("fallback_to_opencv", True)
        self._qt_viewer = None
        self._window_name = config.get("display", {}).get(
            "window_name", "Smart Guide Glasses"
        )
        self._window_created = False

        # 尝试创建 Qt viewer
        if self._mode == "qt":
            self._qt_viewer = create_viewer(config)
            if self._qt_viewer is None and self._fallback_enabled:
                self._mode = "opencv"
                print("[ui] DisplayManager: switched to OpenCV fallback")
            elif self._qt_viewer:
                self._qt_viewer.show()
                print("[qt_viewer] show window")
        else:
            pass

    # ================================================================
    # 属性
    # ================================================================

    @property
    def backend(self) -> str:
        return "qt" if self._qt_viewer else "opencv"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_qt(self) -> bool:
        return self._qt_viewer is not None

    @property
    def qt_viewer(self):
        return self._qt_viewer

    @property
    def window_closed(self) -> bool:
        if self._qt_viewer:
            return self._qt_viewer.window_closed
        return False

    @staticmethod
    def process_events():
        process_qt_events()

    # ================================================================
    # ---- 核心：统一显示接口（main.py 必须使用这些方法）----
    # ================================================================

    def setup_window(self, name: str = None, width: int = 800, height: int = 600):
        """创建显示窗口。Qt 模式已在 __init__ 中完成，OpenCV 模式在此创建。"""
        if name:
            self._window_name = name
        if self.backend == "opencv" and not self._window_created:
            cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(
                self._window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
            )
            self._window_created = True

    def show_frame(self, frame):
        """显示一帧画面。Qt 模式推送到 QtViewer，OpenCV 模式使用 cv2.imshow。"""
        if self.backend == "qt":
            self.update_frame(frame)
            self.process_events()
        else:
            cv2.imshow(self._window_name, frame)

    def get_key(self) -> int:
        """获取按键。Qt 模式返回 0（按键通过 should_quit 的 window_closed 处理），
        OpenCV 模式返回 cv2.waitKey 结果。"""
        if self.backend == "qt":
            self.process_events()
            return 0  # Qt 模式：按键通过 window_closed 检测
        else:
            return cv2.waitKey(1) & 0xFF

    def should_quit(self, key: int = 0) -> bool:
        """判断是否应退出。"""
        if self.backend == "qt":
            return self.window_closed
        else:
            return key == ord("q")

    @staticmethod
    def resize_frame(frame, width: int, height: int):
        """缩放帧到显示尺寸。"""
        return cv2.resize(frame, (width, height))

    def cleanup(self):
        """清理显示资源。"""
        if self.backend == "opencv":
            cv2.destroyAllWindows()
        self.close()

    # ================================================================
    # 原有更新接口（保持兼容）
    # ================================================================

    def update_frame(self, frame):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_frame(frame)
            except Exception:
                pass

    def update_full(self, state: dict):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_full(state)
            except Exception:
                pass

    def update_detection(self, detections: list = None):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_detection(detections)
            except Exception:
                pass

    def update_guide_text(self, text: str = ""):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_guide_text(text)
            except Exception:
                pass

    def update_fps(self, fps: float = 0.0):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_fps(fps)
            except Exception:
                pass

    def update_status(self, status_dict: dict = None):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_status(status_dict)
            except Exception:
                pass

    def update_info(self, detections: list = None, guide_text: str = "",
                    fps: float = 0.0, mode: str = ""):
        if self._qt_viewer:
            try:
                self._qt_viewer.update_info(detections, guide_text, fps, mode)
            except Exception:
                pass

    def close(self):
        if self._qt_viewer:
            try:
                self._qt_viewer.close()
            except Exception:
                pass
