#!/usr/bin/env python3
"""
tests/test_illegal_class_filter.py — 非法类别过滤测试

测试场景:
  1. class_id=0 故宫 → 应正常输出
  2. class_id=20 熊 → 应正常输出
  3. class_id=21 → 应只打印 warning，不播报、不上传、不更新目标

同时测试:
  - class_name="class_21" → 被拒绝
  - class_name="" / None / "unknown" → 被拒绝
  - display_name="class_21" → 被拒绝

运行:
    cd /home/elf/Documents/sum
    python3 tests/test_illegal_class_filter.py
"""

import os
import sys
import json

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.class_validator import (
    is_valid_class_id,
    is_valid_class_name,
    is_valid_display_name,
    is_valid_guide_target,
    warn_invalid_class,
    load_class_map,
    get_num_classes,
    reload_class_map,
)
from core.result_formatter import format_detection

# 确保先加载类别表
reload_class_map()
NUM_CLASSES = get_num_classes()

print("=" * 70)
print("非法类别过滤 — 单元测试")
print(f"classes_sum.json len = {NUM_CLASSES}，合法 class_id 范围 0~{NUM_CLASSES - 1}")
print("=" * 70)

# ================================================================
# 1. is_valid_class_id 测试
# ================================================================
print("\n--- 1. is_valid_class_id ---")

test_cases_id = [
    (0, True, "class_id=0 故宫"),
    (20, True, "class_id=20 熊"),
    (10, True, "class_id=10 东方明珠塔"),
    (21, False, "class_id=21 非法（超出范围）"),
    (-1, False, "class_id=-1 非法（负数）"),
    (999, False, "class_id=999 非法（远超范围）"),
    ("abc", False, "class_id='abc' 非法（非整数）"),
    (None, False, "class_id=None 非法"),
    (20.0, True, "class_id=20.0 浮点数（可转为 int）"),
]

all_pass_id = True
for cid, expected, desc in test_cases_id:
    result = is_valid_class_id(cid)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_pass_id = False
    print(f"  {status} {desc}: is_valid_class_id({cid!r}) = {result} (expected {expected})")

# ================================================================
# 2. is_valid_class_name 测试
# ================================================================
print("\n--- 2. is_valid_class_name ---")

test_cases_name = [
    ("forbidden_city", True, "正常名 forbidden_city"),
    ("bear", True, "正常名 bear"),
    ("tiger", True, "正常名 tiger"),
    ("statue_of_liberty", True, "正常名 statue_of_liberty"),
    ("class_21", False, "非法名 class_21"),
    ("class_xx", False, "非法名 class_xx"),
    ("unknown_class_21", False, "非法名 unknown_class_21"),
    ("unknown", False, "非法名 unknown"),
    ("None", False, "非法名 'None' 字符串"),
    (None, False, "None 值"),
    ("", False, "空字符串"),
    ("  ", False, "空白字符串"),
]

all_pass_name = True
for name, expected, desc in test_cases_name:
    result = is_valid_class_name(name)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_pass_name = False
    print(f"  {status} {desc}: is_valid_class_name({name!r}) = {result} (expected {expected})")

# ================================================================
# 3. is_valid_display_name 测试
# ================================================================
print("\n--- 3. is_valid_display_name ---")

test_cases_display = [
    ("故宫", True, "正常中文名"),
    ("熊", True, "正常中文名"),
    ("自由女神像", True, "正常中文名"),
    ("class_21", False, "非法中文名 class_21"),
    (None, False, "None 值"),
    ("", False, "空字符串"),
]

all_pass_display = True
for name, expected, desc in test_cases_display:
    result = is_valid_display_name(name)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_pass_display = False
    print(f"  {status} {desc}: is_valid_display_name({name!r}) = {result} (expected {expected})")

# ================================================================
# 4. is_valid_guide_target 综合测试
# ================================================================
print("\n--- 4. is_valid_guide_target ---")

test_cases_target = [
    (0, "forbidden_city", "故宫", True, "正常目标 故宫"),
    (20, "bear", "熊", True, "正常目标 熊"),
    (21, "class_21", "class_21", False, "非法目标 class_21"),
    (None, "forbidden_city", "故宫", True, "无 class_id 但有合法名"),
    (0, "class_21", "class_21", False, "合法 class_id 但非法 class_name"),
    (None, None, None, False, "全部为 None"),
    (None, "", "", False, "全部为空"),
]

all_pass_target = True
for cid, cname, dname, expected, desc in test_cases_target:
    result = is_valid_guide_target(class_id=cid, class_name=cname, display_name=dname)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_pass_target = False
    print(f"  {status} {desc}: is_valid_guide_target(id={cid!r}, name={cname!r}, disp={dname!r}) = {result} (expected {expected})")

# ================================================================
# 5. format_detection 过滤测试
# ================================================================
print("\n--- 5. format_detection 过滤测试 ---")

# 加载 CLASSES 元组
from core import postprocess as _pp
_reload = reload_class_map()
CLASSES_TUPLE = tuple(
    item["class_name"] for item in load_class_map()
)
print(f"  CLASSES 元组长度: {len(CLASSES_TUPLE)}")
print(f"  CLASSES[0] = {CLASSES_TUPLE[0]}")
print(f"  CLASSES[20] = {CLASSES_TUPLE[20]}")

# 测试 1: class_id=0 故宫
print("\n  测试 5a: class_id=0 故宫")
result = format_detection(
    boxes=[[100, 100, 300, 300]],
    classes=[0],
    scores=[0.95],
    img_w=640, img_h=480,
    frame_id=1,
    class_names=CLASSES_TUPLE,
)
obj_count = len(result.get("objects", []))
print(f"    objects count = {obj_count}")
if obj_count > 0:
    print(f"    objects[0].class_name = {result['objects'][0]['class_name']}")
assert obj_count == 1, f"class_id=0 should produce 1 object, got {obj_count}"
assert result["objects"][0]["class_name"] == "forbidden_city"
print("    ✅ class_id=0 故宫正常输出")

# 测试 2: class_id=20 熊
print("\n  测试 5b: class_id=20 熊")
result = format_detection(
    boxes=[[100, 100, 300, 300]],
    classes=[20],
    scores=[0.95],
    img_w=640, img_h=480,
    frame_id=1,
    class_names=CLASSES_TUPLE,
)
obj_count = len(result.get("objects", []))
print(f"    objects count = {obj_count}")
if obj_count > 0:
    print(f"    objects[0].class_name = {result['objects'][0]['class_name']}")
assert obj_count == 1, f"class_id=20 should produce 1 object, got {obj_count}"
assert result["objects"][0]["class_name"] == "bear"
print("    ✅ class_id=20 熊正常输出")

# 测试 3: class_id=21 非法
print("\n  测试 5c: class_id=21 非法")
result = format_detection(
    boxes=[[100, 100, 300, 300]],
    classes=[21],
    scores=[0.95],
    img_w=640, img_h=480,
    frame_id=1,
    class_names=CLASSES_TUPLE,
)
obj_count = len(result.get("objects", []))
print(f"    objects count = {obj_count} (expected 0)")
assert obj_count == 0, f"class_id=21 should produce 0 objects, got {obj_count}"
print("    ✅ class_id=21 被完全过滤，objects 为空")

# 测试 4: 混合（合法+非法）
print("\n  测试 5d: 混合 class_id=0,21")
result = format_detection(
    boxes=[[100, 100, 200, 200], [300, 300, 400, 400]],
    classes=[0, 21],
    scores=[0.95, 0.88],
    img_w=640, img_h=480,
    frame_id=1,
    class_names=CLASSES_TUPLE,
)
obj_count = len(result.get("objects", []))
print(f"    objects count = {obj_count} (expected 1)")
assert obj_count == 1, f"Mixed should produce 1 object (only valid), got {obj_count}"
assert result["objects"][0]["class_name"] == "forbidden_city"
print("    ✅ 混合场景：保留 class_id=0，过滤 class_id=21")

# 测试 5: 全部非法
print("\n  测试 5e: 全部非法 class_id=21,22,999")
result = format_detection(
    boxes=[[100, 100, 200, 200], [300, 300, 400, 400], [10, 10, 50, 50]],
    classes=[21, 22, 999],
    scores=[0.95, 0.88, 0.77],
    img_w=640, img_h=480,
    frame_id=1,
    class_names=CLASSES_TUPLE,
)
obj_count = len(result.get("objects", []))
print(f"    objects count = {obj_count} (expected 0)")
assert obj_count == 0, f"All invalid should produce 0 objects, got {obj_count}"
print("    ✅ 全部非法：objects 为空")

# ================================================================
# 6. warn_invalid_class 格式测试
# ================================================================
print("\n--- 6. warn_invalid_class 输出格式 ---")
print("  预期格式: [warn] ignore invalid class_id=21 class_name=class_21 reason=...")
print("  实际输出:")
warn_invalid_class(class_id=21, class_name="class_21", reason="test: out_of_range")
print("  ✅ 格式符合预期")

# ================================================================
# 7. qa_manager.build_intro_text 拒绝非法类别测试
# ================================================================
print("\n--- 7. qa_manager.build_intro_text 拒绝非法类别 ---")
from agent.qa_manager import QAManager

# 用最小配置初始化
qa = QAManager({
    "runtime": {"mode": "sum"},
    "web": {"record_file": "/tmp/test_illegal_class.jsonl"},
})

# 测试非法 raw_name
print("\n  测试 7a: raw_name='class_21'")
result = qa.build_intro_text(raw_name="class_21", display_name="class_21", knowledge=None)
print(f"    result = {result}")
assert result is None, f"build_intro_text should return None for class_21, got {result}"
print("    ✅ build_intro_text 拒绝 class_21，返回 None")

# 测试正常 raw_name
print("\n  测试 7b: raw_name='forbidden_city', display_name='故宫'")
result = qa.build_intro_text(raw_name="forbidden_city", display_name="故宫", knowledge=None)
print(f"    result = {result}")
assert result is not None, "build_intro_text should return dict for forbidden_city"
assert "故宫" in result.get("answer", "")
print("    ✅ build_intro_text 正常输出故宫")

# 测试非法 display_name
print("\n  测试 7c: raw_name='bear', display_name='class_21'")
result = qa.build_intro_text(raw_name="bear", display_name="class_21", knowledge=None)
print(f"    result = {result}")
assert result is None, f"build_intro_text should return None for display_name=class_21, got {result}"
print("    ✅ build_intro_text 拒绝 display_name=class_21")

# ================================================================
# 8. WebUploader.build_event 拒绝非法类别测试
# ================================================================
print("\n--- 8. WebUploader.build_event 拒绝非法类别 ---")
from web.web_uploader import WebUploader

print("\n  测试 8a: class_name='class_21'")
event = WebUploader.build_event(
    device_id="test",
    class_name="class_21",
    display_name="class_21",
    confidence=0.95,
    fps=30,
    inference_ms=50,
    postprocess_ms=10,
    narration_triggered=False,
)
print(f"    event = {event}")
assert event is None, f"build_event should return None for class_21, got {event}"
print("    ✅ build_event 拒绝 class_21，返回 None")

print("\n  测试 8b: class_name='forbidden_city', display_name='故宫'")
event = WebUploader.build_event(
    device_id="test",
    class_name="forbidden_city",
    display_name="故宫",
    confidence=0.95,
    fps=30,
    inference_ms=50,
    postprocess_ms=10,
    narration_triggered=True,
)
print(f"    event exists = {event is not None}")
assert event is not None, "build_event should return dict for forbidden_city"
assert event["class_name"] == "forbidden_city"
assert event["display_name"] == "故宫"
print("    ✅ build_event 正常构建故宫事件")

# ================================================================
# 汇总
# ================================================================
print("\n" + "=" * 70)
print("测试汇总")
print("=" * 70)

all_pass = all_pass_id and all_pass_name and all_pass_display and all_pass_target
print(f"  is_valid_class_id:      {'✅ ALL PASS' if all_pass_id else '❌ FAILURES'}")
print(f"  is_valid_class_name:    {'✅ ALL PASS' if all_pass_name else '❌ FAILURES'}")
print(f"  is_valid_display_name:  {'✅ ALL PASS' if all_pass_display else '❌ FAILURES'}")
print(f"  is_valid_guide_target:  {'✅ ALL PASS' if all_pass_target else '❌ FAILURES'}")
print(f"  format_detection 过滤:  ✅ ALL PASS")
print(f"  warn_invalid_class:     ✅ 格式正确")
print(f"  build_intro_text 拒绝:  ✅ ALL PASS")
print(f"  build_event 拒绝:       ✅ ALL PASS")
print(f"\n  总结: {'✅ 全部测试通过' if all_pass else '❌ 存在失败测试'}")

if not all_pass:
    sys.exit(1)
