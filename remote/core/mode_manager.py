"""
core/mode_manager.py — 识别模式管理器

管理 sum（合并）、scenic（景点）和 animal（动物）三种识别模式的切换。
所有模式共用同一个合并模型（21类: 11景点 + 10动物），使用合并类别表。

使用方式：
    from core.mode_manager import ModeManager

    mgr = ModeManager("sum", config)
    # mgr.classes → 21 个合并类别元组
    # mgr.model_path → /home/elf/Documents/sum/rknnModel/best.rknn
    # mgr.class_map_path → data/class_map/classes_sum.json
    # mgr.knowledge_path → knowledge/sum_knowledge.json
    # mgr.prompt_type → "scenic"
"""

import json
import os
from typing import Optional


# ============================================================================
# 模式定义
# ============================================================================

_MODES = {
    "sum": {
        "name": "合并识别模式（景点+动物）",
        "model_path": "/home/elf/Documents/sum/rknnModel/best.rknn",
        "class_map": "data/class_map/classes_sum.json",
        "knowledge": "knowledge/sum_knowledge.json",
        "prompt_type": "scenic",
        "domain": "landmark",
    },
    "scenic": {
        "name": "景点识别模式",
        "model_path": "/home/elf/Documents/sum/rknnModel/best.rknn",
        "class_map": "data/class_map/classes_sum.json",
        "knowledge": "knowledge/sum_knowledge.json",
        "prompt_type": "scenic",
        "domain": "landmark",
    },
    "animal": {
        "name": "动物识别模式",
        "model_path": "/home/elf/Documents/sum/rknnModel/best.rknn",
        "class_map": "data/class_map/classes_sum.json",
        "knowledge": "knowledge/sum_knowledge.json",
        "prompt_type": "animal",
        "domain": "animal",
    },
}

_VALID_MODES = list(_MODES.keys())


# ============================================================================
# ModeManager 类
# ============================================================================

class ModeManager:
    """识别模式管理器。

    根据 mode 名称提供该模式下所有差异化配置。
    """

    def __init__(self, mode: str, config: dict):
        """
        Args:
            mode:   模式名 "sum"、"scenic" 或 "animal"
            config: 完整配置字典（可选，用于覆盖默认路径）
        """
        if mode not in _MODES:
            raise ValueError(
                f"Unknown mode '{mode}'. Valid: {_VALID_MODES}"
            )

        self._mode = mode
        self._cfg = _MODES[mode]

        # 允许 config 覆盖模型路径
        if config:
            mc = config.get("modes", {}).get(mode, {})
            self._model_path = mc.get("model_path", self._cfg["model_path"])
        else:
            self._model_path = self._cfg["model_path"]

    # ================================================================
    # 属性
    # ================================================================

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def name(self) -> str:
        return self._cfg["name"]

    @property
    def model_path(self) -> str:
        return self._model_path

    @property
    def class_map_path(self) -> str:
        return self._cfg["class_map"]

    @property
    def knowledge_path(self) -> str:
        return self._cfg["knowledge"]

    @property
    def prompt_type(self) -> str:
        return self._cfg["prompt_type"]

    @property
    def domain(self) -> str:
        return self._cfg["domain"]

    # ================================================================
    # 类别加载
    # ================================================================

    def load_classes(self) -> tuple:
        """从 class_map JSON 中提取 CLASSES 元组。

        Returns:
            (raw_class_name, ...) 元组，顺序与 class_id 一致。
        """
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.class_map_path,
        )
        try:
            with open(path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            # 按 class_id 排序
            entries.sort(key=lambda e: e.get("class_id", 0))
            return tuple(e["raw_class_name"] for e in entries)
        except Exception as e:
            print(f"[mode] WARNING: Failed to load classes from {path}: {e}")
            return ()

    def load_class_map_entries(self) -> list:
        """加载完整的类别映射条目列表。"""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.class_map_path,
        )
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[mode] WARNING: Failed to load class map: {e}")
            return []

    # ================================================================
    # 静态工具
    # ================================================================

    @staticmethod
    def get_valid_modes() -> list:
        return _VALID_MODES

    @staticmethod
    def get_default_mode() -> str:
        return "sum"
