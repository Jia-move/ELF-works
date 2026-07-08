"""
core/event_trigger.py — 事件触发判断引擎

根据结构化检测结果判断是否应触发智能体或语音播报。
不实际调用云端 API 或 TTS，仅输出触发判断。

触发规则（优先级从高到低）：
  1. 安全目标出现              → priority=high,   reason=safety_object
  2. 出现新的重要目标           → priority=medium, reason=new_important_object
  3. 主要目标类别变化           → priority=medium, reason=class_changed
  4. 用户强制触发 (force=True)  → priority=high,   reason=user_forced
  5. 距上次触发超过 3×cooldown  → priority=low,    reason=periodic_update

不触发条件：
  - cooldown 期内
  - 无有效目标
  - 目标置信度/大小不足
  - 目标类别与上次完全相同

使用方式：
    from core.event_trigger import EventTrigger

    trigger = EventTrigger(config)
    result = trigger.evaluate(detection_result)
    if result["should_trigger"]:
        print(f"TRIGGER: {result['trigger_reason']} ({result['priority']})")
"""

import time
import threading

# size 等级映射为数值，便于比较
_SIZE_ORDER = {"small": 0, "medium": 1, "large": 2}


class EventTrigger:
    """事件触发判断引擎。

    根据检测结果的时间序列判断是否应触发播报/智能体调用。
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典，读取 event_trigger 节
        """
        ec = config.get("event_trigger", {})

        self.cooldown_seconds = float(ec.get("cooldown_seconds", 5.0))
        self.min_confidence = float(ec.get("min_confidence", 0.3))
        self.min_size = str(ec.get("min_size", "medium"))
        self.important_classes = set(ec.get("important_classes", []))
        self.safety_classes = set(ec.get("safety_classes", []))

        # 状态
        self._lock = threading.Lock()
        self._last_trigger_time = 0.0
        self._last_main_objects = set()  # 上次触发时的主要类别
        self._trigger_count = 0

    # ================================================================
    # 公共接口
    # ================================================================

    def evaluate(self, detection_result: dict, force: bool = False) -> dict:
        """评估当前帧是否应触发播报。

        Args:
            detection_result: format_detection() 返回的结构化结果
            force: 用户主动提问强制触发

        Returns:
            {
                "should_trigger": bool,
                "trigger_reason": str,   # 触发原因或非触发原因
                "priority": str or None, # "high"|"medium"|"low"
                "objects": [str],        # 相关目标类别列表
            }
        """
        objects = detection_result.get("objects", [])
        now = time.time()

        # ---- 强制触发 ----
        if force:
            return self._commit(True, "user_forced", "high",
                                self._class_names(objects),
                                self._class_names(objects), now)

        # ---- 无目标 ----
        if not objects:
            return self._no_trigger("no_objects")

        # ---- 过滤低质量目标 ----
        valid = self._filter_valid(objects)
        if not valid:
            return self._no_trigger("low_confidence_or_size")

        # ---- cooldown 检查 ----
        with self._lock:
            elapsed = now - self._last_trigger_time
        if elapsed < self.cooldown_seconds:
            return self._no_trigger("cooldown")

        # 当前重要目标（配置为空时所有目标都重要）
        current_main = set()
        for o in valid:
            if not self.important_classes or o["class_name"] in self.important_classes:
                current_main.add(o["class_name"])

        # ---- 规则 1: 安全目标（最高优先级）----
        if self.safety_classes:
            safety = [o for o in valid if o["class_name"] in self.safety_classes]
            if safety:
                return self._commit(True, "safety_object", "high",
                                    self._class_names(safety),
                                    current_main, now)

        with self._lock:
            last_main = set(self._last_main_objects)

        # ---- 规则 2: 新重要目标出现 ----
        if current_main and not current_main.issubset(last_main):
            new_classes = current_main - last_main
            return self._commit(True, "new_important_object", "medium",
                                list(new_classes), current_main, now)

        # ---- 规则 3: 主要目标类别变化 ----
        if current_main and current_main != last_main:
            return self._commit(True, "class_changed", "medium",
                                list(current_main), current_main, now)

        # ---- 规则 4: 长间隔周期更新 ----
        if current_main and elapsed >= self.cooldown_seconds * 3:
            return self._commit(True, "periodic_update", "low",
                                list(current_main), current_main, now)

        return self._no_trigger("no_change")

    def reset(self):
        """重置触发状态（用于测试或模式切换）。"""
        with self._lock:
            self._last_trigger_time = 0.0
            self._last_main_objects = set()
            self._trigger_count = 0

    # ================================================================
    # 内部方法
    # ================================================================

    def _filter_valid(self, objects: list) -> list:
        """过滤置信度不足或太小的目标。"""
        min_size_val = _SIZE_ORDER.get(self.min_size, 1)
        result = []
        for o in objects:
            if o["confidence"] < self.min_confidence:
                continue
            if _SIZE_ORDER.get(o.get("size", "small"), 0) < min_size_val:
                continue
            result.append(o)
        return result

    def _commit(self, should_trigger, reason, priority,
                result_objects, state_objects, now):
        """记录触发并返回结果。

        Args:
            result_objects: 输出到 result["objects"] 的类别列表（触发原因相关）
            state_objects:  用于更新 _last_main_objects 的类别集合（全部当前重要类别）
        """
        if should_trigger:
            with self._lock:
                self._last_trigger_time = now
                self._last_main_objects = set(state_objects)
                self._trigger_count += 1
        return {
            "should_trigger": should_trigger,
            "trigger_reason": reason,
            "priority": priority,
            "objects": list(result_objects),
        }

    def _no_trigger(self, reason: str) -> dict:
        """快速构造非触发结果。"""
        return {
            "should_trigger": False,
            "trigger_reason": reason,
            "priority": None,
            "objects": [],
        }

    @staticmethod
    def _class_names(objects: list) -> list:
        """提取目标类别名列表（去重）。"""
        return list(dict.fromkeys(o["class_name"] for o in objects))

    @property
    def trigger_count(self) -> int:
        """已触发次数。"""
        with self._lock:
            return self._trigger_count


def format_trigger_text(result: dict) -> str:
    """将触发结果格式化为单行终端输出字符串。"""
    if result["should_trigger"]:
        objs = ", ".join(result["objects"][:3])
        return (f"[trigger] YES | reason={result['trigger_reason']}"
                f" | priority={result['priority']}"
                f" | objects=[{objs}]")
    else:
        return f"[trigger] NO  | reason={result['trigger_reason']}"
