"""
agent/deepseek_client.py — DeepSeek API 客户端

使用 OpenAI 兼容格式调用 DeepSeek API。
如果未设置 DEEPSEEK_API_KEY 环境变量，自动使用 mock 模式。

使用方式：
    from agent.deepseek_client import DeepSeekClient

    client = DeepSeekClient(config)
    answer = client.chat(messages=[...])  # 返回回答文本
    # 或
    answer = client.answer_question(
        user_question="它有什么历史？",
        context="当前景点：故宫\n知识库：故宫是明清两代...",
        history=[{"role":"user","content":"..."}, ...]
    )
"""

import os
import json
import time
import threading
from typing import Optional


# ============================================================================
# Mock 回答模板（用于无 API Key 场景）
# ============================================================================

_MOCK_QA_TEMPLATES = [
    "根据资料，{detail}",
    "{detail}",
    "据我所知，{detail}，这是该导览目标的重要特色。",
    "{detail}，值得深入了解。",
]

_MOCK_UNKNOWN = [
    "关于{name}，建议您查看旁边的展板说明，或询问现场工作人员获取更准确的信息。",
    "关于{name}的这个问题，现场展板会有更详细的介绍，您也可以询问工作人员。",
    "建议您参考现场展板信息或咨询工作人员，获取关于{name}最准确的介绍。",
]

_MOCK_NO_TARGET = "请先对准一个导览目标，我识别后再为你讲解。"


# ============================================================================
# DeepSeekClient
# ============================================================================

class DeepSeekClient:
    """DeepSeek API 客户端（OpenAI 兼容格式）。

    支持三种模式：
    - live:  DEEPSEEK_API_KEY 已设置 → 调用真实 API
    - mock:  DEEPSEEK_API_KEY 未设置 → 本地规则生成答案
    - fallback: live 模式失败 → 返回安全提示文本
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典，读取 deepseek 节
        """
        dc = config.get("deepseek", {})

        self.enabled = bool(dc.get("enabled", True))

        # base_url: 优先环境变量 DEEPSEEK_BASE_URL，否则用配置
        env_base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip()
        self.base_url = str(env_base_url or dc.get("base_url", "https://api.deepseek.com"))

        # model: 优先环境变量 DEEPSEEK_MODEL，否则用配置
        env_model = os.environ.get("DEEPSEEK_MODEL", "").strip()
        self.model = str(env_model or dc.get("model", "deepseek-v4-flash"))

        self.timeout = float(dc.get("timeout", 20))
        self.max_retries = int(dc.get("max_retries", 1))
        self.temperature = float(dc.get("temperature", 0.3))
        self.max_tokens = int(dc.get("max_tokens", 300))
        self.thinking_type = str(dc.get("thinking", {}).get("type", "disabled"))

        # API Key（仅从环境变量读取）
        self._api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self._has_api_key = bool(self._api_key)

        # 线程安全
        self._lock = threading.Lock()

        if not self._has_api_key:
            print("[deepseek] API key loaded: no  → mock mode")
        else:
            print("[deepseek] API key loaded: yes → live mode")

    # ================================================================
    # 公共接口
    # ================================================================

    @property
    def is_live(self) -> bool:
        """是否使用真实 API。"""
        return self._has_api_key and self.enabled

    def chat(self, messages: list) -> dict:
        """发送多轮对话请求。

        Args:
            messages: [{"role":"system"|"user"|"assistant", "content":str}, ...]

        Returns:
            {"answer": str, "source": "deepseek"|"mock"|"fallback", "model": str}
        """
        if self.is_live:
            return self._live_chat(messages)
        else:
            return self._mock_chat(messages)

    def answer_question(self, user_question: str,
                        context: str = "",
                        history: list = None) -> dict:
        """回答用户导览问题（便捷方法）。

        Args:
            user_question: 用户问题文本
            context:       当前景点上下文（名称、知识库等）
            history:       历史对话列表

        Returns:
            {"answer": str, "source": str, "model": str}
        """
        system_prompt = """
你是智能导览眼镜的讲解助手。
你需要结合「当前导览目标」和「用户问题」回答。

回答原则：
1. 优先使用本地导览知识；
2. 本地知识不足时，可以使用可靠的通用常识补充；
3. 对动物问题，可以回答食物、习性、栖息地、参观安全提醒；
4. 对景点问题，可以回答历史、文化、建筑特色；
5. 不要编造实时信息，例如票价、开放时间、排队情况、现场路线；
6. 如果确实无法确定，才说"建议以现场展板或工作人员说明为准"；
7. 回答控制在 80 到 160 个中文字符，适合语音播报；
8. 不要说"我的知识库中没有详细信息"这种暴露系统内部的话。
""".strip()

        messages = [{"role": "system", "content": system_prompt}]

        # 拼接历史
        if history:
            messages.extend(history)

        # 当前问题
        user_content = user_question
        if context:
            user_content = f"{context}\n\n用户问题：{user_question}"
        messages.append({"role": "user", "content": user_content})

        return self.chat(messages)

    # ================================================================
    # Live 模式
    # ================================================================

    def _live_chat(self, messages: list) -> dict:
        """调用 DeepSeek API。"""

        # 构建 thinking 参数
        thinking = None
        if self.thinking_type == "enabled":
            thinking = {"type": "enabled"}
        elif self.thinking_type == "disabled":
            thinking = None  # 不传 thinking 参数
        else:
            thinking = {"type": self.thinking_type}

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if thinking is not None:
            payload["thinking"] = thinking

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                import urllib.request
                import urllib.error

                url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
                data = json.dumps(payload).encode("utf-8")

                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    answer = body["choices"][0]["message"]["content"]
                    return {
                        "answer": answer.strip(),
                        "source": "deepseek",
                        "model": self.model,
                    }

            except urllib.error.HTTPError as e:
                last_error = e
                body_str = ""
                try:
                    body_str = e.read().decode("utf-8")[:200]
                except Exception:
                    pass
                print(f"[deepseek] HTTP {e.code}: {body_str}")
                if e.code == 401:
                    break  # 认证失败，不重试
                if e.code == 402:
                    break  # 额度不足，不重试
                if attempt < self.max_retries:
                    time.sleep(1)

            except Exception as e:
                last_error = e
                print(f"[deepseek] Request failed: {e}")
                if attempt < self.max_retries:
                    time.sleep(1)

        # 所有重试失败 → fallback
        err_msg = str(last_error) if last_error else "unknown"
        print(f"[deepseek] All attempts failed: {err_msg}")
        return self._fallback()

    # ================================================================
    # Mock 模式
    # ================================================================

    def _mock_chat(self, messages: list) -> dict:
        """本地规则生成答案。"""
        # 提取用户问题
        user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_content = m.get("content", "")
                break

        # 尝试从上下文中提取景点名称
        import re
        name_match = re.search(r"当前(?:导览)?目标[：:]\s*(\S+)", user_content)
        name = name_match.group(1) if name_match else ""

        # 提取知识库内容
        kb_match = re.search(r"知识库[内容]*[：:]\s*(.+?)(?:用户问题|$)", user_content, re.DOTALL)
        kb_text = kb_match.group(1).strip() if kb_match else ""

        question = user_content.split("用户问题：")[-1].strip() if "用户问题：" in user_content else user_content

        if not name:
            return {"answer": _MOCK_NO_TARGET, "source": "mock", "model": "local/mock"}

        if kb_text and len(kb_text) > 10:
            # 有知识库：用模板拼接
            import random
            detail = kb_text[:80].rstrip("。，,;；") + "。"
            template = random.choice(_MOCK_QA_TEMPLATES)
            answer = template.format(name=name, detail=detail)
            return {"answer": answer, "source": "knowledge_base", "model": "local/mock"}
        else:
            import random
            template = random.choice(_MOCK_UNKNOWN)
            answer = template.format(name=name) if name else template
            return {"answer": answer, "source": "mock", "model": "local/mock"}

    # ================================================================
    # Fallback
    # ================================================================

    @staticmethod
    def _fallback() -> dict:
        """任何异常返回安全 fallback 文本。"""
        return {
            "answer": "抱歉，云端服务暂时不可用。已为你保留本地识别结果，请稍后再试。",
            "source": "fallback",
            "model": "fallback",
        }
