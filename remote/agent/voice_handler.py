"""
agent/voice_handler.py — 语音问答处理器

编排完整的语音问答流程：
  录音 → PCM 转换 → 讯飞 ASR → 文本问答 → 音箱播报

使用方式：
    from agent.voice_handler import VoiceHandler

    vh = VoiceHandler(config)
    result = vh.process_voice_question()
    # result: {"answer": str, "question": str, "success": bool, "error": str}
"""

import os
import re
import sys
import time


# ============================================================================
# ASR 文本清洗
# ============================================================================

def clean_asr_text(raw_text: str) -> str:
    """清理 ASR 识别文本中的常见错误。

    处理：
    1. 连续重复字符去重（"他他" → "他"）
    2. 代词修正（"他/她" → "它"，导览语境下目标通常用"它"）
    3. 尝试提取核心问题（去除口吃式重复前缀）

    Args:
        raw_text: ASR 原始识别文本

    Returns:
        清洗后的文本
    """
    if not raw_text:
        return raw_text

    # Step 1: 连续重复字符去重
    cleaned = re.sub(r'(.)\1+', r'\1', raw_text)

    # Step 2: 代词修正（在导览语境中，目标通常用"它"）
    cleaned = cleaned.replace("他", "它").replace("她", "它")

    # Step 3: 去除口吃式连续重复片段（如 "它以它以" → "它以"）
    # 从长到短尝试不同窗口大小
    for window in [3, 2]:
        i = 0
        safety = 0
        while i + window * 2 <= len(cleaned) and safety < 100:
            safety += 1
            if cleaned[i:i+window] == cleaned[i+window:i+window*2]:
                # 发现连续重复片段，移除一份
                cleaned = cleaned[:i+window] + cleaned[i+window*2:]
                # 不递增 i，因为移除后可能在同位置出现新的重复
            else:
                i += 1

    return cleaned


# ============================================================================
# VoiceHandler
# ============================================================================

class VoiceHandler:
    """语音问答处理器。

    编排完整流程：
    1. 录音（mic_recorder）
    2. 语音转文字（xfyun_asr_client）
    3. 智能问答（qa_manager → deepseek）
    4. 语音播报（speaker）

    失败时 fallback 到文本输入。
    """

    # 语音处理状态（用于 UI 显示）
    STATUS_IDLE = "idle"
    STATUS_LISTENING = "listening"
    STATUS_RECOGNIZING = "recognizing"
    STATUS_THINKING = "thinking"
    STATUS_SPEAKING = "speaking"

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典
        """
        self._config = config
        self._status = self.STATUS_IDLE

        # 音频配置
        ac = config.get("audio", {})
        self._input_device = ac.get("input_device", "plughw:4,0")
        self._record_seconds = int(ac.get("record_seconds", 5))

        # ASR 配置
        asc = config.get("asr", {})
        self._asr_enabled = bool(asc.get("enabled", True))

        # QA 配置
        qc = config.get("qa", {})
        self._voice_enabled = bool(qc.get("voice_enabled", True))
        self._fallback_to_text = bool(qc.get("fallback_to_text", True))

    # ================================================================
    # 公共接口
    # ================================================================

    @property
    def status(self) -> str:
        """当前语音处理状态。"""
        return self._status

    def process_voice_question(self) -> dict:
        """执行完整语音问答流程。

        Returns:
            {
                "success": bool,
                "question": str,       # ASR 识别出的问题文本
                "answer": str,         # 最终回答文本
                "answer_source": str,  # "deepseek"|"mock"|"local"|"fallback"
                "error": str | None,   # 错误信息
            }
        """
        # ---- Step 1: 录音 ----
        self._status = self.STATUS_LISTENING
        print("[voice] 🎤 Step 1/4: 正在聆听...")

        try:
            pcm_path = self._record_audio()
        except Exception as e:
            error_msg = f"录音失败: {e}"
            print(f"[voice] ❌ {error_msg}")
            self._status = self.STATUS_IDLE
            return self._fallback_result(error_msg)

        # ---- Step 2: ASR 识别 ----
        self._status = self.STATUS_RECOGNIZING
        print("[voice] 🔍 Step 2/4: 正在识别...")

        try:
            question = self._transcribe(pcm_path)
        except Exception as e:
            error_msg = f"语音识别失败: {e}"
            print(f"[voice] ❌ {error_msg}")
            self._status = self.STATUS_IDLE
            return self._fallback_result(error_msg)

        if not question or not question.strip():
            error_msg = "语音识别失败，请重试或使用文本输入"
            print(f"[voice] ❌ {error_msg}")
            self._status = self.STATUS_IDLE
            return self._fallback_result(error_msg)

        print(f"[voice] ✅ ASR 识别文本: {question}")

        # ---- Step 2.5: 清洗 ASR 文本 ----
        raw_question = question
        cleaned_question = clean_asr_text(question)
        if cleaned_question != raw_question:
            print(f"[voice] 🔧 ASR 清洗: {raw_question} → {cleaned_question}")
            # 将原始和清洗后的文本一起传给 DeepSeek，让它根据语境理解
            question = (
                f"用户语音识别原文：{raw_question}\n\n"
                f"请根据语境理解用户意图并回答：{cleaned_question}"
            )
        else:
            question = cleaned_question

        # ---- Step 3: 智能问答 ----
        self._status = self.STATUS_THINKING
        print(f"[voice] 💭 Step 3/4: 正在思考...")

        try:
            qa_result = self._ask_deepseek(question)
        except Exception as e:
            error_msg = f"智能回答暂时不可用: {e}"
            print(f"[voice] ❌ {error_msg}")
            self._status = self.STATUS_IDLE
            return {
                "success": False,
                "question": question,
                "answer": "智能回答暂时不可用，请稍后重试",
                "answer_source": "fallback",
                "error": error_msg,
            }

        answer = qa_result.get("answer", "")
        answer_source = qa_result.get("source", "unknown")

        print(f"[voice] ✅ 回答: {answer}")

        # ---- Step 4: 播报 ----
        self._status = self.STATUS_SPEAKING
        print(f"[voice] 🔊 Step 4/4: 正在播报...")

        # 播报由调用方负责（通过 speaker 对象），这里只返回结果

        self._status = self.STATUS_IDLE
        return {
            "success": True,
            "question": question,
            "raw_asr_text": raw_question,
            "cleaned_question": cleaned_question,
            "answer": answer,
            "answer_source": answer_source,
            "error": None,
        }

    # ================================================================
    # 内部方法
    # ================================================================

    def _record_audio(self) -> str:
        """录音并返回 PCM 文件路径。

        传递完整 config 给 MicRecorder，使其优先使用
        parecord + Redmi PulseAudio source 录音。
        """
        from audio.mic_recorder import MicRecorder

        recorder = MicRecorder(
            config=self._config,
            device=self._input_device,
        )
        return recorder.record(duration=self._record_seconds)

    def _transcribe(self, pcm_path: str) -> str:
        """调用讯飞 ASR 转写 PCM 音频。"""
        if not self._asr_enabled:
            raise RuntimeError("ASR 未启用（config asr.enabled=false）")

        from agent.xfyun_asr_client import XfyunAsrClient

        client = XfyunAsrClient()
        result = client.recognize(pcm_path)

        if not result.get("success"):
            error = result.get("error", "未知错误")
            raise RuntimeError(f"语音识别失败，请重试或使用文本输入 ({error})")

        return result.get("text", "").strip()

    def _ask_deepseek(self, question: str) -> dict:
        """调用 QAManager 回答语音识别出的问题。

        注意：这里使用当前导览目标上下文（通过 GuideSession 获取），
        确保回答与当前识别的目标相关。
        """
        from core.guide_session import get_session
        from agent.qa_manager import QAManager

        session = get_session()

        # 构造一个简化的 qa_manager 调用
        qa = QAManager(self._config)

        # 如果有当前目标，使用标准问答流程
        if session.current_display_name:
            result = qa.handle_question(question)
            if result:
                return result

        # 无目标时
        result = qa.handle_unknown_target_question(question)
        if result:
            return result

        return {"answer": "智能回答暂时不可用，请稍后重试", "source": "fallback"}

    def _fallback_result(self, error_msg: str) -> dict:
        """构造 fallback 结果。"""
        if self._fallback_to_text:
            hint = "，请使用文本输入"
        else:
            hint = ""
        return {
            "success": False,
            "question": "",
            "answer": f"语音识别失败{hint}",
            "answer_source": "fallback",
            "error": error_msg,
        }


# ============================================================================
# 便捷函数
# ============================================================================

def _get_display_state():
    """延迟获取 DisplayState（避免循环导入）。"""
    from core.visualizer import get_display_state
    return get_display_state()
