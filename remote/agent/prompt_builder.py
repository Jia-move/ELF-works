"""
agent/prompt_builder.py — 智能体 Prompt 生成器

将结构化检测结果、位置、导览知识和用户问题组装为适合
云端大模型理解的中文 Prompt。不负责调用 API，仅输出 Prompt 文本。

使用方式：
    from agent.prompt_builder import build_prompt

    prompt = build_prompt(
        detection_result=result,
        location="故宫太和殿前广场",
        landmark_knowledge="太和殿是故宫最大的宫殿，建于明朝永乐年间...",
        user_question=None,
        trigger_result=trigger,
    )
    # 将 prompt 发送给云端大模型
"""

from typing import Optional


# ============================================================================
# 场景描述模板
# ============================================================================

def _describe_objects(objects: list, class_names_cn: dict = None) -> str:
    """将检测目标列表转换为中文方位描述。

    Args:
        objects: [{"class_name": str, "position": str, "confidence": float}, ...]
        class_names_cn: {英文名: 中文名} 映射，如 {"The Forbidden City": "故宫"}

    Returns:
        中文场景描述如 "左侧故宫，中央长城"
    """
    if not objects:
        return "未检测到特定目标"

    position_cn = {
        "left": "左侧", "right": "右侧", "center": "前方",
        "front-left": "左前方", "front-right": "右前方",
    }
    cn_map = class_names_cn or {}
    top3 = objects[:3]
    parts = []
    for obj in top3:
        pos = position_cn.get(obj.get("position", ""), "")
        raw_name = obj.get("class_name", "未知")
        name = cn_map.get(raw_name, raw_name)
        parts.append(f"{pos}{name}" if pos else name)
    return "，".join(parts)


def _describe_safety(objects: list) -> str:
    """生成安全目标的中文描述。

    Args:
        objects: 字符串列表（如 ['car', 'obstacle']）
    """
    return "、".join(str(o) for o in objects[:3])


# ============================================================================
# Prompt 构建
# ============================================================================

def build_prompt(
    detection_result: Optional[dict] = None,
    location: Optional[str] = None,
    landmark_knowledge: Optional[str] = None,
    user_question: Optional[str] = None,
    trigger_result: Optional[dict] = None,
    class_names_cn: Optional[dict] = None,
    prompt_type: str = "scenic",
) -> str:
    """构建发送给云端大模型的中文 Prompt。

    Args:
        detection_result: format_detection() 的输出
        location:         当前位置描述，可为空
        landmark_knowledge: 检索到的知识文本，可为空
        user_question:    用户当前提问，可为空
        trigger_result:   EventTrigger.evaluate() 的输出，可为空
        class_names_cn:   {英文名: 中文名} 映射
        prompt_type:      "scenic" | "animal"

    Returns:
        中文 Prompt 字符串
    """
    is_animal = (prompt_type == "animal")
    parts = ["你是智能导览眼镜助手。\n"]

    # ---- 1. 场景描述 ----
    objects = detection_result.get("objects", []) if detection_result else []
    if objects:
        scene = _describe_objects(objects, class_names_cn)
        parts.append(f"当前场景：{scene}。\n")
    else:
        parts.append("当前场景：未检测到特定目标。\n")

    # ---- 2. 位置信息 ----
    if location:
        parts.append(f"当前位置：{location}。\n")

    # ---- 3. 安全优先 ----
    is_safety = (
        trigger_result
        and trigger_result.get("should_trigger")
        and trigger_result.get("trigger_reason") == "safety_object"
    )
    if is_safety:
        safety_names = _describe_safety(trigger_result.get("objects", []))
        parts.append(f"⚠️ 检测到安全风险目标：{safety_names}。请优先生成安全提醒。\n")

    # ---- 4. 用户提问优先 ----
    if user_question:
        parts.append(f"用户提问：{user_question}\n")
        parts.append("请优先回答用户问题。如有安全风险也必须提醒。\n")

    # ---- 5. 知识库（有则引导介绍，无则禁止编造）----
    if landmark_knowledge:
        if is_animal:
            parts.append(f"动物知识参考：{landmark_knowledge}\n")
            parts.append("请基于上述知识生成动物介绍，并提醒用户保持安全距离。\n")
        else:
            parts.append(f"导览知识参考：{landmark_knowledge}\n")
            parts.append("请基于上述知识生成导览介绍。\n")
    else:
        parts.append("请勿编造介绍信息，只描述识别结果和安全建议。\n")

    # ---- 6. 输出约束 ----
    is_qa = bool(user_question)
    if is_qa:
        parts.append("请直接回答问题，语言简洁自然。输出控制在 50 字以内。\n")
    elif is_animal:
        parts.append("请生成一句简短中文语音提示（30-80字），包含动物介绍和安全提醒。不要输出过长内容。\n")
    else:
        parts.append("请生成一句简短中文语音提示（30-80字），优先安全提醒再导览建议。不要输出过长内容。\n")

    return "".join(parts)
