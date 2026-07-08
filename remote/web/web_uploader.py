"""
web/web_uploader.py — 非阻塞 Web 上传器

将识别事件和心跳通过 HTTP 上传到电脑 Web 后端。
所有网络请求在独立后台线程中执行，不阻塞主识别线程。

架构:
    主线程 (触发点)               后台线程
    ───────────────               ──────────
    uploader.enqueue(event)  →    queue.Queue(maxsize=100)
    (put_nowait, 非阻塞)     →    _worker() loop:
                                  ├─ queue.get(timeout=0.5)
                                  ├─ POST /api/device/events
                                  └─ 失败 → 重试 → 丢弃 → 日志

    uploader._heartbeat_loop() → 定时器线程
                                  └─ POST /api/devices/heartbeat (每 N 秒)

核心约束:
    - 不影响本地识别、Qt 显示、知识库讲解、speaker、问答
    - Web 后端不可达时本地功能继续正常运行
    - 主识别线程不被 HTTP 请求阻塞
    - enabled: false 时不创建任何线程

使用方式:
    from web.web_uploader import WebUploader

    uploader = WebUploader(config, mode="scenic")
    # ... 触发时 ...
    uploader.enqueue(event_dict)
    # ... 退出时 ...
    uploader.shutdown()
"""

import json
import queue
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

from core.class_validator import is_valid_class_name, is_valid_display_name, warn_invalid_class


class WebUploader:
    """非阻塞 Web 上传器。

    特性:
        - 独立后台线程处理所有 HTTP 请求
        - queue.Queue(maxsize) 有界队列，put_nowait 非阻塞入队
        - 队列满时丢弃最旧事件 + dropped_count 计数
        - 心跳与识别事件分开处理（独立定时器）
        - enabled: false 时零开销（不创建线程）
        - shutdown 安全退出，不阻塞主程序
    """

    # 默认状态（heartbeat 使用）
    DEFAULT_STATUS = {
        "camera_status": "ok",
        "npu_status": "running",
        "qt_status": "stopped",
        "qa_status": "available",
        "asr_status": "unsupported",
        "software_version": "1.0.0",
    }

    def __init__(self, config: dict, mode: str = "scenic"):
        """
        Args:
            config: 完整配置字典，读取 web_upload 节
            mode:   当前识别模式 "scenic" | "animal"
        """
        wc = config.get("web_upload", {})

        self._enabled = bool(wc.get("enabled", False))
        self._base_url = str(wc.get("base_url", "http://localhost:8000")).rstrip("/")
        self._device_id = str(wc.get("device_id", "elf2-01"))
        self._heartbeat_interval = float(wc.get("heartbeat_interval_sec", 10))
        self._connect_timeout = float(wc.get("connect_timeout_sec", 2))
        self._read_timeout = float(wc.get("read_timeout_sec", 5))
        self._queue_maxsize = int(wc.get("queue_maxsize", 100))
        self._retry_count = int(wc.get("retry_count", 3))
        self._source = str(wc.get("source", "rknn"))

        self._mode = mode

        # 线程安全的状态存储（heartbeat 线程读取，主线程更新）
        self._lock = threading.Lock()
        self._status = dict(self.DEFAULT_STATUS)

        # 从 config 提取模型文件名
        model_path = config.get("model", {}).get("path", "best.rknn")
        self._model_name = model_path.split("/")[-1] if "/" in model_path else model_path

        # 统计计数器
        self._enqueued_count = 0
        self._sent_count = 0
        self._failed_count = 0
        self._dropped_count = 0

        # 仅在启用时创建线程和队列
        if not self._enabled:
            self._queue = None
            self._shutdown_event = None
            self._worker_thread = None
            self._heartbeat_timer = None
            print("[web_upload] disabled — no upload threads created")
            return

        # 有界事件队列
        self._queue = queue.Queue(maxsize=self._queue_maxsize)

        # 退出信号
        self._shutdown_event = threading.Event()

        # 启动工作线程（daemon 以确保主线程退出时不被阻塞）
        self._worker_thread = threading.Thread(
            target=self._worker,
            name="web-uploader-worker",
            daemon=True,
        )
        self._worker_thread.start()

        # 启动心跳定时器（daemon 线程 + sleep 循环）
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="web-uploader-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

        print(f"[web_upload] enabled — "
              f"base_url={self._base_url}, "
              f"device_id={self._device_id}, "
              f"mode={self._mode}, "
              f"queue_maxsize={self._queue_maxsize}, "
              f"heartbeat_interval={self._heartbeat_interval}s")

    # ================================================================
    # 公共接口
    # ================================================================

    @property
    def enabled(self) -> bool:
        """是否已启用上传。"""
        return self._enabled

    @property
    def device_id(self) -> str:
        """设备标识。"""
        return self._device_id

    def set_mode(self, mode: str):
        """更新当前识别模式（由主线程在切换模式时调用）。"""
        self._mode = mode

    def update_status(self, **kwargs):
        """更新心跳上报的状态字段（线程安全）。

        可更新字段:
            camera_status, npu_status, qt_status,
            qa_status, asr_status, software_version
        """
        with self._lock:
            self._status.update(kwargs)

    def enqueue(self, event: dict) -> bool:
        """将识别事件放入上传队列（非阻塞）。

        队列满时丢弃最旧事件，增加 dropped_count。

        Args:
            event: 识别事件 dict，需包含 event_id, device_id, captured_at 等

        Returns:
            True 表示成功入队，False 表示已禁用或队列满
        """
        if not self._enabled:
            return False

        try:
            self._queue.put_nowait(event)
            self._enqueued_count += 1
            return True
        except queue.Full:
            # 丢弃最旧事件，放入新事件
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self._dropped_count += 1
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(event)
                self._enqueued_count += 1
            except queue.Full:
                self._dropped_count += 1
                print(f"[web_upload] WARNING: queue still full after discard, "
                      f"dropped_count={self._dropped_count}")
            return False

    def shutdown(self, timeout: float = 5.0):
        """安全关闭上传器。

        1. 设置退出信号
        2. 等待工作线程结束（timeout 秒）
        3. 打印统计摘要

        Args:
            timeout: 等待线程结束的最大秒数
        """
        if not self._enabled:
            return

        print(f"[web_upload] shutting down... "
              f"(enqueued={self._enqueued_count}, "
              f"sent={self._sent_count}, "
              f"failed={self._failed_count}, "
              f"dropped={self._dropped_count})")

        # 发出退出信号
        if self._shutdown_event is not None:
            self._shutdown_event.set()

        # 向队列放入哨兵以唤醒 worker（如果它阻塞在 get 上）
        if self._queue is not None:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

        # 等待工作线程
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                print("[web_upload] WARNING: worker thread did not exit in time")

        # 等待心跳线程
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=min(timeout, 2.0))
            if self._heartbeat_thread.is_alive():
                print("[web_upload] WARNING: heartbeat thread did not exit in time")

        print(f"[web_upload] shutdown complete. "
              f"Final: sent={self._sent_count}, "
              f"failed={self._failed_count}, "
              f"dropped={self._dropped_count}")

    # ================================================================
    # 统计属性
    # ================================================================

    @property
    def stats(self) -> dict:
        """返回当前统计信息快照。"""
        return {
            "enabled": self._enabled,
            "enqueued": self._enqueued_count,
            "sent": self._sent_count,
            "failed": self._failed_count,
            "dropped": self._dropped_count,
            "queue_depth": self._queue.qsize() if self._queue else 0,
        }

    # ================================================================
    # 工作线程
    # ================================================================

    def _worker(self):
        """后台工作线程：从队列取事件，发送到 Web 后端。

        循环直到 shutdown_event 被设置。
        队列为空时阻塞在 get(timeout=0.5)。
        所有异常静默捕获，绝不向上抛出。
        """
        while not self._shutdown_event.is_set():
            try:
                event = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue  # 超时，重新检查退出信号

            # 哨兵值（shutdown 时放入）
            if event is None:
                break

            # 尝试发送
            success = self._post_event(event)
            if success:
                self._sent_count += 1
            else:
                self._failed_count += 1
                print(f"[web_upload] WARNING: failed to send event "
                      f"event_id={event.get('event_id', '?')}, "
                      f"failed_count={self._failed_count}")

            self._queue.task_done()

    def _post_event(self, event: dict) -> bool:
        """POST 识别事件到后端，带重试。

        Args:
            event: 识别事件 dict

        Returns:
            True 表示发送成功，False 表示失败
        """
        url = f"{self._base_url}/api/device/events"

        for attempt in range(self._retry_count):
            try:
                data = json.dumps(event, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                with urllib.request.urlopen(
                    req, timeout=self._connect_timeout + self._read_timeout
                ) as resp:
                    if 200 <= resp.status < 300:
                        return True
                    else:
                        print(f"[web_upload] WARNING: POST events → HTTP {resp.status} "
                              f"(attempt {attempt + 1}/{self._retry_count})")
            except urllib.error.HTTPError as e:
                print(f"[web_upload] WARNING: POST events → HTTP {e.code} "
                      f"(attempt {attempt + 1}/{self._retry_count})")
            except (urllib.error.URLError, OSError, ConnectionError,
                    TimeoutError, Exception) as e:
                msg = str(e)[:120]
                print(f"[web_upload] WARNING: POST events → {msg} "
                      f"(attempt {attempt + 1}/{self._retry_count})")

            # 重试前退避
            if attempt < self._retry_count - 1:
                backoff = min(2 ** attempt, 8)  # 1s → 2s → 4s → 8s → max 8s
                if not self._shutdown_event.wait(timeout=backoff):
                    continue  # 未被中断，继续重试
                else:
                    break      # shutdown 信号，停止重试

        return False

    # ================================================================
    # 心跳
    # ================================================================

    def _heartbeat_loop(self):
        """心跳线程：定期 POST 设备状态到后端。

        循环直到 shutdown_event 被设置。
        首次心跳立即发送，后续按 heartbeat_interval 间隔。
        失败不影响下次尝试。
        """
        # 首次心跳延迟减半，快速上线
        first = True

        while not self._shutdown_event.is_set():
            if first:
                # 首次延迟 1 秒（等待系统稳定）
                if self._shutdown_event.wait(timeout=1.0):
                    break
                first = False
            else:
                # 正常间隔
                if self._shutdown_event.wait(timeout=self._heartbeat_interval):
                    break

            self._send_heartbeat()

    def _send_heartbeat(self):
        """构造并发送一次心跳。"""
        with self._lock:
            status = dict(self._status)

        heartbeat = {
            "device_id": self._device_id,
            "sent_at": self._utc_now(),
            "software_version": status.get("software_version", "1.0.0"),
            "model_name": self._model_name,
            "mode": self._mode,
            "camera_status": status.get("camera_status", "ok"),
            "npu_status": status.get("npu_status", "running"),
            "qt_status": status.get("qt_status", "stopped"),
            "qa_status": status.get("qa_status", "available"),
            "asr_status": status.get("asr_status", "unsupported"),
        }

        url = f"{self._base_url}/api/devices/heartbeat"

        try:
            data = json.dumps(heartbeat, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(
                req, timeout=self._connect_timeout + self._read_timeout
            ) as resp:
                if 200 <= resp.status < 300:
                    print(f"[web_upload] heartbeat ok "
                          f"(mode={self._mode}, device={self._device_id})")
                else:
                    print(f"[web_upload] WARNING: heartbeat → HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            print(f"[web_upload] WARNING: heartbeat → HTTP {e.code}")
        except (urllib.error.URLError, OSError, ConnectionError,
                TimeoutError, Exception) as e:
            msg = str(e)[:120]
            print(f"[web_upload] WARNING: heartbeat → {msg}")

    # ================================================================
    # 问答记录上传
    # ================================================================

    def upload_qa_record(self, question: str, answer: str,
                         scenic_name: str = "",
                         provider: str = "text_deepseek") -> bool:
        """上传问答记录到 Windows 后端（非阻塞，失败不影响主程序）。

        POST /api/qa-records

        Args:
            question:    用户问题文本（语音问答时为 ASR 识别结果）
            answer:      DeepSeek 回答文本
            scenic_name: 当前导览目标中文名
            provider:    来源标识: "text_deepseek" | "voice_xfyun_deepseek"

        Returns:
            True 表示上传成功，False 表示失败
        """
        if not self._enabled:
            return False

        payload = {
            "device_id": self._device_id,
            "question": question,
            "answer": answer,
            "scenic_name": scenic_name or "",
            "provider": provider,
        }

        url = f"{self._base_url}/api/qa-records"

        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(
                req, timeout=self._connect_timeout + self._read_timeout
            ) as resp:
                if 200 <= resp.status < 300:
                    print(f"[qa_upload] success (provider={provider}, "
                          f"scenic={scenic_name or '(none)'})")
                    return True
                else:
                    print(f"[qa_upload] failed: HTTP {resp.status}")
                    return False
        except urllib.error.HTTPError as e:
            print(f"[qa_upload] failed: HTTP {e.code}")
            return False
        except (urllib.error.URLError, OSError, ConnectionError,
                TimeoutError, Exception) as e:
            msg = str(e)[:120]
            print(f"[qa_upload] failed: {msg}")
            return False

    # ================================================================
    # 工具方法
    # ================================================================

    @staticmethod
    def _utc_now() -> str:
        """返回 UTC ISO-8601 格式的时间戳。"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ================================================================
    # 静态事件构建器
    # ================================================================

    @staticmethod
    def build_event(device_id: str,
                    class_name: str,
                    display_name: str,
                    confidence: float,
                    fps: float,
                    inference_ms: float,
                    postprocess_ms: float,
                    narration_triggered: bool,
                    source: str = "rknn") -> dict:
        """构建标准识别事件 dict。

        如果 class_name 或 display_name 非法，返回 None（调用方应跳过上传）。

        Args:
            device_id:           设备标识
            class_name:          模型原始英文类别名
            display_name:        中文展示名
            confidence:          置信度
            fps:                 瞬时 FPS
            inference_ms:        NPU 推理耗时 (ms)
            postprocess_ms:      后处理耗时 (ms)
            narration_triggered: 是否已触发语音播报
            source:              数据来源，固定 "rknn"

        Returns:
            标准事件 dict（含 event_id 和 captured_at），或 None（类别非法）
        """
        # ---- 防御：拒绝非法类别名 ----
        if not is_valid_class_name(class_name):
            warn_invalid_class(class_name=class_name,
                               reason="invalid class_name in WebUploader.build_event")
            return None
        if display_name and not is_valid_display_name(display_name):
            warn_invalid_class(display_name=display_name,
                               reason="invalid display_name in WebUploader.build_event")
            return None

        import uuid
        return {
            "event_id": uuid.uuid4().hex,
            "device_id": device_id,
            "captured_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "class_name": class_name,
            "display_name": display_name,
            "confidence": round(float(confidence), 4),
            "fps": round(float(fps), 2),
            "inference_ms": round(float(inference_ms), 2),
            "postprocess_ms": round(float(postprocess_ms), 2),
            "narration_triggered": bool(narration_triggered),
            "source": source,
        }
