"""
agent/knowledge_base.py — 本地景点知识库查询模块

提供模型类别名 → 中文名 → 景点介绍的查询接口。
所有数据来源于 data/class_map/ 和 knowledge/ 目录下的 JSON 文件。

使用方式：
    from agent.knowledge_base import (
        load_class_map, load_landmarks,
        normalize_class_name, get_landmark_by_raw_class,
    )

    info = get_landmark_by_raw_class("The Forbidden City")
    if info:
        print(info["display_name"])  # 故宫
        print(info["intro"])         # 故宫是明清两代...
"""

import json
import os
from typing import Optional


# ============================================================================
# 路径配置（相对于项目根目录）
# ============================================================================

def _project_root() -> str:
    """获取项目根目录。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_CLASS_MAP_PATH = os.path.join("data", "class_map", "classes_landmark.json")
_LANDMARKS_PATH = os.path.join("knowledge", "landmarks.json")

# 内存缓存
_class_map_cache: Optional[list] = None
_landmarks_cache: Optional[list] = None
_raw_name_index: Optional[dict] = None
_class_name_index: Optional[dict] = None


# ============================================================================
# 加载函数
# ============================================================================

def _resolve_path(relative_path: str) -> str:
    """解析相对于项目根目录的路径。"""
    return os.path.join(_project_root(), relative_path)


def load_class_map(force_reload: bool = False) -> list:
    """加载类别映射表。

    Args:
        force_reload: 强制重新从文件加载

    Returns:
        list of dict，格式见 data/class_map/classes_landmark.json
        加载失败时返回空列表
    """
    global _class_map_cache
    if _class_map_cache is not None and not force_reload:
        return _class_map_cache

    path = _resolve_path(_CLASS_MAP_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            _class_map_cache = json.load(f)
        return _class_map_cache
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[knowledge] WARNING: Failed to load class map '{path}': {e}")
        _class_map_cache = []
        return _class_map_cache


def set_knowledge_path(path: str):
    """设置知识库文件路径并清除缓存。

    Args:
        path: 相对于项目根目录的知识库路径，如 "knowledge/animal_knowledge.json"
    """
    global _LANDMARKS_PATH, _landmarks_cache, _class_name_index
    _LANDMARKS_PATH = path
    _landmarks_cache = None
    _class_name_index = None


def set_class_map_path(path: str):
    """设置类别映射文件路径并清除缓存。

    Args:
        path: 相对于项目根目录的类别映射路径
    """
    global _CLASS_MAP_PATH, _class_map_cache, _raw_name_index
    _CLASS_MAP_PATH = path
    _class_map_cache = None
    _raw_name_index = None


def load_landmarks(force_reload: bool = False) -> list:
    """加载知识库。

    Args:
        force_reload: 强制重新从文件加载

    Returns:
        list of dict
        加载失败时返回空列表
    """
    global _landmarks_cache
    if _landmarks_cache is not None and not force_reload:
        return _landmarks_cache

    path = _resolve_path(_LANDMARKS_PATH)
    try:
        with open(path, "r", encoding="utf-8") as f:
            _landmarks_cache = json.load(f)
        return _landmarks_cache
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[knowledge] WARNING: Failed to load landmarks '{path}': {e}")
        _landmarks_cache = []
        return _landmarks_cache


# ============================================================================
# 索引构建
# ============================================================================

def _build_raw_name_index() -> dict:
    """构建 raw_class_name → class_map_entry 索引。"""
    global _raw_name_index
    if _raw_name_index is not None:
        return _raw_name_index

    class_map = load_class_map()
    _raw_name_index = {}
    for entry in class_map:
        _raw_name_index[entry["raw_class_name"]] = entry
    return _raw_name_index


def _build_class_name_index() -> dict:
    """构建 class_name → landmark_entry 索引。"""
    global _class_name_index
    if _class_name_index is not None:
        return _class_name_index

    landmarks = load_landmarks()
    _class_name_index = {}
    for entry in landmarks:
        _class_name_index[entry["class_name"]] = entry
    return _class_name_index


# ============================================================================
# 查询函数
# ============================================================================

def normalize_class_name(raw_class_name: str) -> Optional[str]:
    """将模型输出的原始英文类别名转换为标准化 class_name。

    Args:
        raw_class_name: 模型 CLASSES 中的英文名，如 "The Forbidden City"

    Returns:
        标准化名称如 "forbidden_city"，未找到返回 None
    """
    index = _build_raw_name_index()
    entry = index.get(raw_class_name)
    return entry["class_name"] if entry else None


def get_landmark_by_raw_class(raw_class_name: str) -> Optional[dict]:
    """根据模型原始类别名查询景点信息。

    Args:
        raw_class_name: 模型 CLASSES 中的英文名

    Returns:
        dict 包含 class_name, display_name, intro, features，
        未找到返回 None
    """
    index = _build_raw_name_index()
    class_entry = index.get(raw_class_name)
    if not class_entry:
        return None

    landmark_index = _build_class_name_index()
    landmark = landmark_index.get(class_entry["class_name"])
    if not landmark:
        return None

    return {
        "class_name": landmark["class_name"],
        "display_name": landmark["display_name"],
        "intro": landmark["intro"],
        "features": landmark.get("features", []),
        "tips": landmark.get("tips", ""),
        "raw_class_name": raw_class_name,
    }


def get_landmark_by_class_name(class_name: str) -> Optional[dict]:
    """根据标准化类别名查询景点信息。

    Args:
        class_name: 标准化名称如 "forbidden_city"

    Returns:
        dict 包含 class_name, display_name, intro, features，
        未找到返回 None
    """
    landmark_index = _build_class_name_index()
    landmark = landmark_index.get(class_name)
    if not landmark:
        return None

    # 反向查找 raw_class_name
    raw_name = None
    for entry in load_class_map():
        if entry["class_name"] == class_name:
            raw_name = entry["raw_class_name"]
            break

    return {
        "class_name": landmark["class_name"],
        "display_name": landmark["display_name"],
        "intro": landmark["intro"],
        "features": landmark.get("features", []),
        "tips": landmark.get("tips", ""),
        "raw_class_name": raw_name,
    }
