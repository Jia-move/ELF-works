"""
core/input_thread.py — 非阻塞终端输入线程

在独立线程中等待用户通过 stdin 输入问题，
通过线程安全队列传递给主线程，不阻塞摄像头画面。

支持两种交互方式：
  - 直接输入文字：触发文本问答
  - 输入 /voice：触发语音问答（录音 → ASR → 问答）
  - 输入 q：退出问答模式

使用方式：
    from core.input_thread import InputThread

    ith = InputThread()
    ith.start()
    # 主循环中：
    question = ith.get_question()  # 非阻塞，无输入返回 ""
    # 退出时：
    ith.stop()
"""

import sys
import threading
import queue
import select


class InputThread:
    """非阻塞终端输入线程。

    在独立线程中读取 stdin，将用户问题放入线程安全队列。
    主线程通过 get_question() 非阻塞获取。

    特殊命令：
    - /voice：触发语音问答
    - q / quit / exit：退出问答模式
    """

    # 语音问答触发标记
    VOICE_TRIGGER = "__voice_trigger__"
    # 退出问答模式标记
    QA_EXIT = "__qa_exit__"

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread = threading.Thread(
            target=self._run, name="input-thread", daemon=True
        )
        self._running = False
        self._prompt_shown = False

    # ================================================================
    # 生命周期
    # ================================================================

    def start(self):
        """启动输入线程。"""
        if self._running:
            return
        self._stop_event.clear()
        self._thread.start()
        self._running = True

    def stop(self):
        """停止输入线程。"""
        self._stop_event.set()
        self._running = False

    # ================================================================
    # 主线程接口
    # ================================================================

    def get_question(self) -> str:
        """非阻塞获取用户输入的问题。

        Returns:
            用户输入的字符串，无输入时返回空字符串 ""。
            特殊值:
            - "__voice_trigger__": 用户输入了 /voice
            - "__qa_exit__": 用户输入了 q/quit/exit
        """
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return ""

    # ================================================================
    # 内部
    # ================================================================

    def _run(self):
        """线程主循环：等待 stdin 输入。"""
        # 首次进入时打印提示
        print("[qa] 输入 /voice 触发语音问答，直接输入文字触发文本问答，按 q 退出：")
        print("[qa] > ", end="", flush=True)

        while not self._stop_event.is_set():
            try:
                # 使用 select 检查 stdin 是否有数据（超时 0.5s）
                if sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]:
                    line = sys.stdin.readline()
                    if line:
                        question = line.strip()
                        if question:
                            if question.lower() in ("q", "quit", "exit"):
                                print("[qa] 退出问答模式，继续导览。")
                                self._queue.put(self.QA_EXIT)
                            elif question.strip() == "/voice":
                                print("[qa] 🎤 触发语音问答...")
                                self._queue.put(self.VOICE_TRIGGER)
                            else:
                                self._queue.put(question)
                            # 重新打印提示
                            print("[qa] > ", end="", flush=True)
            except (IOError, OSError):
                # stdin 不可用（如无终端环境），静默退出
                break
            except Exception:
                break
