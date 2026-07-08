"""
core/interaction_logger.py — 交互日志记录器

将每次自动介绍和问答写入 JSONL 文件，供 Web 端读取展示。

线程安全，写入失败不影响主流程。

使用方式：
    from core.interaction_logger import InteractionLogger

    logger = InteractionLogger("logs/guide_interactions.jsonl")
    logger.log_intro(object_raw="The Forbidden City", ...)
    logger.log_qa(object_raw="The Forbidden City", question="...", answer="...")
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional


class InteractionLogger:
    """交互日志记录器（线程安全）。

    写入格式为每行一个 JSON 对象（JSONL）。
    """

    def __init__(self, log_path: str = "logs/guide_interactions.jsonl",
                 device_id: str = "rk3588_glasses_001"):
        """
        Args:
            log_path:  JSONL 日志文件路径
            device_id: 设备标识
        """
        self._log_path = log_path
        self._device_id = device_id
        self._lock = threading.Lock()

    # ================================================================
    # 日志写入
    # ================================================================

    def log_intro(self, *,
                  mode: str = "scenic",
                  object_raw: str = "",
                  object_name: str = "",
                  knowledge_used: bool = False,
                  intro_text: str = "",
                  source: str = "knowledge_base",
                  model: str = "local/mock",
                  fps: float = 0.0,
                  confidence: float = 0.0):
        """记录一次自动介绍事件。

        Args:
            mode:           识别模式
            object_raw:     模型原始类别名
            object_name:    中文展示名
            knowledge_used: 是否使用了知识库
            intro_text:     介绍文本
            source:         文本来源 (knowledge_base / mock / fallback)
            model:          使用的模型
            fps:            当前 FPS
            confidence:     识别置信度
        """
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": self._device_id,
            "mode": mode,
            "event_type": "intro",
            "object_raw": object_raw,
            "object_name": object_name,
            "confidence": round(float(confidence), 4),
            "knowledge_used": knowledge_used,
            "user_question": None,
            "assistant_answer": intro_text,
            "source": source,
            "model": model,
            "fps": round(float(fps), 1),
        }
        self._write(record)

    def log_qa(self, *,
               mode: str = "scenic",
               object_raw: str = "",
               object_name: str = "",
               knowledge_used: bool = False,
               user_question: str = "",
               assistant_answer: str = "",
               source: str = "mock",
               model: str = "local/mock",
               fps: float = 0.0,
               confidence: float = 0.0):
        """记录一次问答事件。

        Args:
            mode:             识别模式
            object_raw:       模型原始类别名
            object_name:      中文展示名
            knowledge_used:   是否使用了知识库
            user_question:    用户问题
            assistant_answer: 助手回答
            source:           回答来源 (deepseek / knowledge_base / mock / fallback)
            model:            使用的模型名
            fps:              当前 FPS
            confidence:       当前识别置信度
        """
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": self._device_id,
            "mode": mode,
            "event_type": "qa",
            "object_raw": object_raw,
            "object_name": object_name,
            "confidence": round(float(confidence), 4),
            "knowledge_used": knowledge_used,
            "user_question": user_question,
            "assistant_answer": assistant_answer,
            "source": source,
            "model": model,
            "fps": round(float(fps), 1),
        }
        self._write(record)

    # ================================================================
    # 内部
    # ================================================================

    def _write(self, record: dict):
        """线程安全地追加一行 JSONL。"""
        try:
            with self._lock:
                # 确保目录存在
                dirname = os.path.dirname(self._log_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 日志绝不阻塞主流程

    # ================================================================
    # 查询（供 Web 端使用）
    # ================================================================

    def load_recent(self, limit: int = 50) -> list:
        """读取最近的交互记录。

        Args:
            limit: 最大返回条数

        Returns:
            list of dict（按时间倒序）
        """
        records = []
        try:
            if not os.path.exists(self._log_path):
                return records
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            records.reverse()
            return records[:limit]
        except Exception:
            return []
