"""
agent/cloud_client.py — 云端智能体客户端

提供统一接口 generate_guide_text(prompt)，默认使用 Mock 模式。
支持 mock / cloud / fallback 三种运行路径。

使用方式：
    from agent.cloud_client import CloudAgentClient

    client = CloudAgentClient(config)
    text = client.generate_guide_text(prompt)
"""

import os
import random

# ============================================================================
# Mock 响应库（简单关键词匹配）
# ============================================================================

_MOCK_SAFETY = [
    "请注意前方安全，检测到障碍物，建议绕行。",
    "前方有安全风险，请减速观察，确认安全后通过。",
    "⚠️ 安全提醒：检测到前方有车辆，请注意避让。",
    "前方检测到行人，请保持安全距离。",
]

_MOCK_LANDMARK = [
    "前方是{name}，这里是著名的世界文化遗产，值得驻足欣赏。",
    "您正前方是{name}，建筑风格独特，历史悠久。",
    "前方{name}，建议您走近参观，了解更多故事。",
    "检测到{name}，这是该地区的地标性建筑。",
]

_MOCK_IDLE = [
    "前方视野开阔，暂未检测到特殊目标。",
    "当前环境安全，您可以继续前行。",
    "未发现特定导览目标或障碍物，请留意周围环境。",
]

_MOCK_QA = [
    "关于您的问题，根据已知信息，{name}是一处著名的文化地标。",
    "根据资料，{name}具有重要的历史价值，值得深入了解。",
    "您问到的{name}，其建筑风格和历史背景非常独特。",
]

_FALLBACK_TEXT = "当前网络不可用，已为你保留本地识别结果，请注意前方环境。"


# ============================================================================
# 客户端类
# ============================================================================

class CloudAgentClient:
    """云端智能体客户端。

    支持三种模式：
    - mock:    根据 Prompt 关键词返回预设导览文本（默认）
    - cloud:   调用真实云端 LLM API（仅预留接口，待实现）
    - fallback: 任何异常返回安全提示文本
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典，读取 agent 节
        """
        ac = config.get("agent", {})

        self.mode = str(ac.get("mode", "mock"))
        self.timeout = float(ac.get("timeout_seconds", 5))
        self.api_key_env = str(ac.get("api_key_env", "GUIDE_AGENT_API_KEY"))
        self.enable_cloud = bool(ac.get("enable_cloud", False))

    # ================================================================
    # 公共接口
    # ================================================================

    def generate_guide_text(self, prompt: str) -> str:
        """生成导览文本。

        Args:
            prompt: build_prompt() 输出的中文 Prompt

        Returns:
            导览文本字符串（50-100 字）
        """
        try:
            if self.mode == "cloud" and self.enable_cloud:
                return self._cloud_call(prompt)
            else:
                return self._mock_response(prompt)
        except Exception:
            return self._fallback()

    # ================================================================
    # Mock 模式
    # ================================================================

    def _mock_response(self, prompt: str) -> str:
        """根据 Prompt 关键词返回模拟导览文本。"""
        # 提取目标名称（从 "当前场景：xxx检测到YYY" 中提取）
        name = self._extract_landmark_name(prompt)

        # 安全风险优先
        if "安全风险" in prompt or "safety" in prompt.lower():
            return random.choice(_MOCK_SAFETY)

        # 用户提问
        if "用户提问" in prompt and name:
            return random.choice(_MOCK_QA).format(name=name)

        # 导览介绍
        if name and "导览知识" in prompt:
            return random.choice(_MOCK_LANDMARK).format(name=name)

        # 普通检测（有目标但无知识）
        if name:
            return f"前方检测到{name}，请留意周围环境。"

        # 空场景
        return random.choice(_MOCK_IDLE)

    # ================================================================
    # 云端模式（仅预留接口）
    # ================================================================

    def _cloud_call(self, prompt: str) -> str:
        """调用真实云端 LLM API。

        TODO: 实现真实 HTTP 请求。
        当前为预留接口，直接返回 fallback。
        """
        # 预留实现：
        # api_key = os.environ.get(self.api_key_env)
        # if not api_key:
        #     return self._fallback()
        # response = requests.post(
        #     "https://api.example.com/v1/chat",
        #     headers={"Authorization": f"Bearer {api_key}"},
        #     json={"prompt": prompt, "max_tokens": 80},
        #     timeout=self.timeout,
        # )
        # return response.json()["text"]
        return self._fallback()

    # ================================================================
    # 内部工具
    # ================================================================

    @staticmethod
    def _extract_landmark_name(prompt: str) -> str:
        """从 Prompt 中提取第一个景点/目标名称。"""
        # 尝试从 "前方The Forbidden City" 或 "左侧car" 等模式中提取
        import re
        # 匹配方位词后的英文/中文名称
        match = re.search(r"(?:前方|左侧|右侧|左前方|右前方)([\w\s]+?)(?:[。，,]|$)", prompt)
        if match:
            name = match.group(1).strip()
            if name and name not in ("检测到", "未检测到", "安全"):
                return name
        return ""

    @staticmethod
    def _fallback() -> str:
        """返回 fallback 文本。"""
        return _FALLBACK_TEXT
