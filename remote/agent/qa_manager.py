"""
agent/qa_manager.py — 问答管理器

统筹问答流程：接收用户问题 → 读取会话上下文 → 构造 prompt →
调用 DeepSeek API → 更新历史 → 返回回答 → 写入日志。

使用方式：
    from agent.qa_manager import QAManager

    qa = QAManager(config)
    result = qa.handle_question("它有什么历史？")
    if result:
        print(result["answer"])
        speaker.speak(result["answer"])
"""

from typing import Optional

from core.class_validator import (is_valid_class_name, is_valid_display_name,
                                   warn_invalid_class)


class QAManager:
    """问答管理器。

    负责：
    - 接收用户问题
    - 读取 GuideSession 当前景点上下文
    - 构造问答 prompt
    - 调用 DeepSeekClient
    - 更新 conversation_history
    - 写入 InteractionLogger
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典
        """
        self._config = config

        # 延迟导入（避免循环依赖）
        from core.guide_session import get_session
        from agent.deepseek_client import DeepSeekClient
        from core.interaction_logger import InteractionLogger

        self._session = get_session()
        self._deepseek = DeepSeekClient(config)

        log_path = config.get("web", {}).get(
            "record_file", "logs/guide_interactions.jsonl"
        ).replace("guide_records.jsonl", "guide_interactions.jsonl")
        # 如果 record_file 还是默认值，使用 logs/guide_interactions.jsonl
        if "guide_records" in log_path:
            log_path = "logs/guide_interactions.jsonl"
        self._logger = InteractionLogger(log_path=log_path)

        self._mode = config.get("runtime", {}).get("mode", "scenic")

    # ================================================================
    # 公共接口
    # ================================================================

    def handle_question(self, user_question: str,
                        fps: float = 0.0) -> Optional[dict]:
        """处理用户问题。

        Args:
            user_question: 用户输入的问题文本
            fps:           当前 FPS（用于日志记录）

        Returns:
            {"answer": str, "source": str, "model": str} 或 None
        """
        if not user_question or not user_question.strip():
            return None

        question = user_question.strip()

        # ---- 检查是否有当前景点 ----
        ctx = self._session.get_context_for_prompt()
        display_name = ctx.get("display_name", "")
        knowledge = ctx.get("knowledge")

        if not display_name:
            answer = "请先对准一个导览目标，我识别后再为你讲解。"
            self._log_qa(user_question, answer, source="local")
            return {"answer": answer, "source": "local", "model": "local/fallback"}

        # ---- 构造上下文 ----
        context_lines = [f"当前导览目标：{display_name}"]

        if knowledge:
            intro = knowledge.get("intro", "")
            features = knowledge.get("features", [])
            tips = knowledge.get("tips", "")
            if intro:
                context_lines.append(f"本地知识：{intro}")
            if features:
                context_lines.append(f"特色：{'、'.join(features)}")
            if tips:
                context_lines.append(f"参观提示：{tips}")
            knowledge_used = True
        else:
            context_lines.append("本地知识：暂无详细资料，请根据通用常识回答。")
            knowledge_used = False

        context = "\n".join(context_lines)

        # ---- 调用 DeepSeek ----
        history = ctx.get("history", [])
        result = self._deepseek.answer_question(
            user_question=question,
            context=context,
            history=history,
        )

        answer = result.get("answer", "")

        # ---- 更新会话历史 ----
        self._session.add_qa_turn(question, answer)

        # ---- 写入日志 ----
        raw_name = ctx.get("object_raw", "")
        self._log_qa(
            user_question=question,
            assistant_answer=answer,
            object_raw=raw_name,
            object_name=display_name,
            knowledge_used=knowledge_used,
            source=result.get("source", "unknown"),
            model=result.get("model", "unknown"),
            fps=fps,
            confidence=ctx.get("confidence", 0.0),
        )

        return result

    def handle_unknown_target_question(self, user_question: str,
                                       fps: float = 0.0) -> dict:
        """处理没有识别目标时的用户提问。

        Returns:
            {"answer": str, "source": str, "model": str}
        """
        answer = "请先对准一个导览目标，我识别后再为你讲解。"
        self._log_qa(
            user_question=user_question,
            assistant_answer=answer,
            object_raw="",
            object_name="",
            knowledge_used=False,
            source="local",
            model="local/fallback",
            fps=fps,
        )
        return {"answer": answer, "source": "local", "model": "local/fallback"}

    # ================================================================
    # 自动介绍
    # ================================================================

    def build_intro_text(self, raw_name: str, display_name: str,
                         knowledge: Optional[dict] = None) -> dict:
        """为识别到的景点生成自动介绍文本。

        Args:
            raw_name:     模型原始类别名
            display_name: 中文展示名
            knowledge:    知识库条目

        Returns:
            {"answer": str, "source": str}
            如果 raw_name 或 display_name 非法，返回 None
        """
        # ---- 防御：拒绝非法类别名 ----
        if not is_valid_class_name(raw_name):
            warn_invalid_class(class_name=raw_name,
                               reason="invalid class_name in build_intro_text")
            return None
        if display_name and not is_valid_display_name(display_name):
            warn_invalid_class(display_name=display_name,
                               reason="invalid display_name in build_intro_text")
            return None

        if knowledge:
            intro = knowledge.get("intro", "")
            tips = knowledge.get("tips", "")
            if intro:
                text = f"前方是{display_name}，{intro}"
                if tips:
                    text += f" {tips}"
                # 截断到 80 字
                if len(text) > 80:
                    # 尝试在句号处截断
                    cut = text.rfind("。", 0, 80)
                    if cut > 40:
                        text = text[:cut + 1]
                    else:
                        text = text[:77] + "..."
                return {"answer": text, "source": "knowledge_base"}
            else:
                return {
                    "answer": f"已识别到{display_name}，但暂无详细资料。",
                    "source": "local",
                }
        else:
            return {
                "answer": f"前方检测到{display_name}，请留意周围环境。",
                "source": "local",
            }

    def log_intro(self, raw_name: str, display_name: str,
                  intro_text: str, knowledge_used: bool,
                  fps: float = 0.0, confidence: float = 0.0,
                  source: str = "knowledge_base"):
        """写入自动介绍日志。"""
        self._logger.log_intro(
            mode=self._mode,
            object_raw=raw_name,
            object_name=display_name,
            knowledge_used=knowledge_used,
            intro_text=intro_text,
            source=source,
            model="local/mock",
            fps=fps,
            confidence=confidence,
        )

    # ================================================================
    # 内部
    # ================================================================

    def _log_qa(self, user_question: str, assistant_answer: str,
                object_raw: str = "", object_name: str = "",
                knowledge_used: bool = False,
                source: str = "mock", model: str = "local/mock",
                fps: float = 0.0, confidence: float = 0.0):
        """写入问答日志（异常不影响主流程）。"""
        try:
            self._logger.log_qa(
                mode=self._mode,
                object_raw=object_raw,
                object_name=object_name,
                knowledge_used=knowledge_used,
                user_question=user_question,
                assistant_answer=assistant_answer,
                source=source,
                model=model,
                fps=fps,
                confidence=confidence,
            )
        except Exception:
            pass
