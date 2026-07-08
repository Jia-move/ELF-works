"""
core/camera.py — 摄像头采集模块

封装 OpenCV VideoCapture，提供统一的摄像头读写接口。

使用方式：
    from core.camera import CameraCapture

    cam = CameraCapture("/dev/video21")
    while cam.is_opened:
        ret, frame = cam.read()
        if not ret:
            break
    cam.release()
"""

import cv2


class CameraCapture:
    """摄像头采集器。

    封装 cv2.VideoCapture，提供带错误处理的帧读取接口。
    """

    def __init__(self, camera_id):
        """
        Args:
            camera_id: 摄像头设备路径（如 "/dev/video21"）或整数索引（如 0）
        """
        self._camera_id = camera_id
        self._cap = cv2.VideoCapture(camera_id)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera: {camera_id}")

    @property
    def is_opened(self) -> bool:
        """摄像头是否已打开。"""
        return self._cap.isOpened()

    def read(self):
        """读取一帧。

        Returns:
            (ret, frame): ret 为 bool，frame 为 BGR numpy array。
                          ret=False 表示读取失败。
        """
        return self._cap.read()

    def release(self):
        """释放摄像头资源。"""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __del__(self):
        self.release()
