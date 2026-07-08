"""
core/class_validator.py — 类别合法性验证模块

统一的类别验证函数，防止非法 class_id / class_name 进入播报、Web 上传、
导览目标更新、DeepSeek context 等下游管线。

使用方式：
    from core.class_validator import (is_valid_class_id, is_valid_class_name,
                                      is_valid_guide_target, get_num_classes)

    if not is_valid_class_id(class_id):
        print(f"[warn] ignore invalid class_id={class_id}")

    if not is_valid_guide_target(class_id, class_name, display_name):
        return  # skip
"""

import json
import os
from typing import Optional

# ============================================================================
# 模块级缓存
# ============================================================================

_classes_cache: Optional[list] = None
_classes_len_cache: int = 0


def _get_classes_path() -> str:
    """获取类别表 JSON 文件路径。"""
    return _resolve_path("data/class_map/classes_sum.json")


def _resolve_path(relative_path: str) -> str:
    """解析相对于项目根目录的路径。"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, relative_path)


def load_class_map() -> list:
    """加载类别映射表 JSON（带模块级缓存）。"""
    global _classes_cache, _classes_len_cache
    if _classes_cache is not None:
        return _classes_cache

    path = _get_classes_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            _classes_cache = json.load(f)
        _classes_len_cache = len(_classes_cache)
        return _classes_cache
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[validator] WARNING: cannot load class map '{path}': {e}")
        _classes_cache = []
        _classes_len_cache = 0
        return _classes_cache


def get_num_classes() -> int:
    """返回当前类别表的长度。"""
    global _classes_len_cache
    if _classes_len_cache > 0:
        return _classes_len_cache
    cmap = load_class_map()
    return len(cmap)


def reload_class_map() -> int:
    """强制重新加载类别表，返回类别数量。"""
    global _classes_cache, _classes_len_cache
    _classes_cache = None
    _classes_len_cache = 0
    return get_num_classes()


# ============================================================================
# 核心验证函数
# ============================================================================

def is_valid_class_id(class_id) -> bool:
    """检查 class_id 是否在合法范围内。

    Args:
        class_id: 类别序号（int 或可转换的类型）

    Returns:
        True 表示 0 <= class_id < num_classes
    """
    if not isinstance(class_id, int):
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            return False
    num = get_num_classes()
    if num <= 0:
        # 如果类别表未加载，不阻塞系统运行
        return True
    return 0 <= class_id < num


def is_valid_class_name(name) -> bool:
    """检查类别名是否合法（非空、非保留垃圾名）。

    拒绝以下模式：
    - None / 空字符串 / "None" / "null" / "unknown"
    - 以 "class_" 开头（如 class_21）
    - 以 "unknown_class_" 开头

    Args:
        name: 类别名字符串
    """
    if not name:
        return False
    if not isinstance(name, str):
        return False
    name_stripped = name.strip()
    if not name_stripped:
        return False
    name_lower = name_stripped.lower()
    if name_lower in ("none", "null", "unknown", "n/a", ""):
        return False
    if name_lower.startswith("class_") or name_lower.startswith("unknown_class_"):
        return False
    return True


def is_valid_display_name(name) -> bool:
    """检查中文展示名是否合法。规则同 is_valid_class_name。"""
    return is_valid_class_name(name)


def is_valid_guide_target(class_id=None, class_name: str = "",
                          display_name: str = "",
                          allow_unknown_knowledge: bool = True) -> bool:
    """综合验证一个导览目标是否合法。

    要求：
    - class_id 必须在合法范围内（如果提供了 class_id）
    - class_name 必须通过 is_valid_class_name
    - display_name 必须通过 is_valid_display_name
    - 三者中至少有一个不为空

    Args:
        class_id:    类别序号（可选，None 时不检查）
        class_name:  类别名（如 "forbidden_city" 或 "class_21"）
        display_name: 中文展示名
        allow_unknown_knowledge: 是否允许知识库中查不到的类别（保留参数，默认 True）

    Returns:
        True 表示目标合法，可进入下游管线
    """
    # class_id 检查（如果提供了）
    if class_id is not None and not is_valid_class_id(class_id):
        return False

    # class_name 检查
    if class_name and not is_valid_class_name(class_name):
        return False

    # display_name 检查
    if display_name and not is_valid_display_name(display_name):
        return False

    # 两者都为空也不行
    if not class_name and not display_name:
        return False

    return True


# ============================================================================
# 终端警告
# ============================================================================

def warn_invalid_class(class_id=None, class_name: str = "",
                       display_name: str = "", reason: str = ""):
    """打印统一格式的非法类别警告。

    格式：[warn] ignore invalid class_id=21 class_name=class_21 reason=out_of_range
    """
    parts = ["[warn] ignore invalid"]
    if class_id is not None:
        parts.append(f"class_id={class_id}")
    if class_name:
        parts.append(f"class_name={class_name}")
    if display_name:
        parts.append(f"display_name={display_name}")
    if reason:
        parts.append(f"reason={reason}")
    print(" ".join(parts))
