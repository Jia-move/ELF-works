"""
core/guide_session.py — 导览会话状态管理

保存当前识别上下文、介绍状态、问答会话历史。
线程安全，供主线程、QA 线程、日志线程访问。

使用方式：
    from core.guide_session import get_session

    session = get_session()
    session.start_intro("The Forbidden City", "故宫", knowledge_dict, intro_text)
    # ... 播报完成后 ...
    session.set_qa_active(True)
    session.add_qa_turn("它有什么历史？", "故宫始建于明代永乐年间...")
"""

import time
import threading
from typing import Optional


class GuideSession:
    """导览会话状态管理器（线程安全）。"""

    def __init__(self):
        self._lock = threading.Lock()

        # ---- 当前识别上下文 ----
        self._current_object_raw: str = ""       # 模型原始类别名，如 "The Forbidden City"
        self._current_display_name: str = ""      # 中文展示名，如 "故宫"
        self._current_knowledge: Optional[dict] = None  # 知识库条目
        self._current_confidence: float = 0.0

        # ---- 自动介绍状态 ----
        self._last_intro_text: str = ""
        self._last_intro_time: float = 0.0

        # ---- 问答状态 ----
        self._qa_active: bool = False
        self._qa_start_time: float = 0.0
        self._conversation_history: list = []  # [{"role":"user"/"assistant", "content":str}]
        self._max_history_turns: int = 5       # 保留最近 N 轮

    # ================================================================
    # 属性（线程安全读写）
    # ================================================================

    @property
    def current_object_raw(self) -> str:
        with self._lock:
            return self._current_object_raw

    @property
    def current_display_name(self) -> str:
        with self._lock:
            return self._current_display_name

    @property
    def current_knowledge(self) -> Optional[dict]:
        with self._lock:
            return dict(self._current_knowledge) if self._current_knowledge else None

    @property
    def current_confidence(self) -> float:
        with self._lock:
            return self._current_confidence

    @property
    def last_intro_text(self) -> str:
        with self._lock:
            return self._last_intro_text

    @property
    def qa_active(self) -> bool:
        with self._lock:
            return self._qa_active

    @property
    def conversation_history(self) -> list:
        with self._lock:
            return list(self._conversation_history)

    # ================================================================
    # 场景更新
    # ================================================================

    def update_current_object(self, raw_name: str, display_name: str,
                              knowledge: Optional[dict] = None,
                              confidence: float = 0.0):
        """更新当前识别到的目标。

        Args:
            raw_name:     模型原始类别名
            display_name: 中文展示名
            knowledge:    知识库条目 dict（含 intro/tips/features）
            confidence:   置信度
        """
        with self._lock:
            self._current_object_raw = raw_name
            self._current_display_name = display_name
            self._current_knowledge = dict(knowledge) if knowledge else None
            self._current_confidence = confidence

    def clear_current_object(self):
        """清除当前识别目标（目标消失时调用）。"""
        with self._lock:
            self._current_object_raw = ""
            self._current_display_name = ""
            self._current_knowledge = None
            self._current_confidence = 0.0
            self._qa_active = False

    # ================================================================
    # 自动介绍
    # ================================================================

    def record_intro(self, text: str):
        """记录最近一次自动介绍文本和时间。"""
        with self._lock:
            self._last_intro_text = text
            self._last_intro_time = time.time()

    @property
    def last_intro_time(self) -> float:
        with self._lock:
            return self._last_intro_time

    # ================================================================
    # 问答状态
    # ================================================================

    def set_qa_active(self, active: bool):
        """设置问答状态。"""
        with self._lock:
            self._qa_active = active
            if active:
                self._qa_start_time = time.time()

    def is_qa_active(self) -> bool:
        with self._lock:
            return self._qa_active

    def add_qa_turn(self, user_question: str, assistant_answer: str):
        """追加一轮问答到历史。

        Args:
            user_question:    用户问题
            assistant_answer: 助手回答
        """
        with self._lock:
            self._conversation_history.append({
                "role": "user",
                "content": user_question,
            })
            self._conversation_history.append({
                "role": "assistant",
                "content": assistant_answer,
            })
            # 保留最近 N 轮
            max_messages = self._max_history_turns * 2
            if len(self._conversation_history) > max_messages:
                self._conversation_history = self._conversation_history[-max_messages:]

    def reset_conversation(self):
        """重置问答历史（景点切换时调用）。"""
        with self._lock:
            self._conversation_history = []
            self._qa_active = False

    # ================================================================
    # 会话摘要（供 prompt 使用）
    # ================================================================

    def get_context_for_prompt(self) -> dict:
        """获取当前上下文的摘要，供 prompt_builder 或 qa_manager 使用。

        Returns:
            dict 包含:
                object_raw, display_name, knowledge, intro_text,
                qa_active, history
        """
        with self._lock:
            return {
                "object_raw": self._current_object_raw,
                "display_name": self._current_display_name,
                "knowledge": (dict(self._current_knowledge)
                              if self._current_knowledge else None),
                "confidence": self._current_confidence,
                "intro_text": self._last_intro_text,
                "qa_active": self._qa_active,
                "history": list(self._conversation_history),
            }


# ============================================================================
# 全局单例
# ============================================================================

_global_session = GuideSession()


def get_session() -> GuideSession:
    """获取全局 GuideSession 单例。"""
    return _global_session
