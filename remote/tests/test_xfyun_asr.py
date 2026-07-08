#!/usr/bin/env python3
"""
test_xfyun_asr.py — 讯飞实时语音转写大模型独立测试脚本
========================================================

功能：
  1. 检查环境变量是否存在
  2. 调用 mic_recorder 录音（5 秒）
  3. 调用 xfyun_asr_client 转文字
  4. 打印识别出的文本
  5. 不调用 DeepSeek，先只测 ASR

测试命令：
  cd /home/elf/Documents/sum
  python3 tests/test_xfyun_asr.py

测试时对着小米音响说：
  "自由女神像有什么历史意义？"

期望输出：
  ASR text: 自由女神像有什么历史意义？

失败时有详细错误信息，帮助排查。
"""

import os
import sys
import time

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================================
# 主测试流程
# ============================================================================

def main():
    print()
    print("=" * 60)
    print("  讯飞实时语音转写大模型 ASR 独立测试")
    print("=" * 60)
    print()

    # ================================================================
    # Step 1: 检查环境变量
    # ================================================================
    print("━" * 60)
    print("Step 1/5: 检查环境变量")
    print("━" * 60)

    required_vars = [
        "XFYUN_ASR_APP_ID",
        "XFYUN_ASR_ACCESS_KEY_ID",
        "XFYUN_ASR_ACCESS_KEY_SECRET",
    ]

    optional_vars = [
        "XFYUN_ASR_URL",
    ]

    all_ok = True
    for var in required_vars:
        value = os.environ.get(var, "")
        if value:
            masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
            print(f"  ✅ {var} = {masked}")
        else:
            print(f"  ❌ {var} 未设置")
            all_ok = False

    for var in optional_vars:
        value = os.environ.get(var, "")
        if value:
            print(f"  ⚪ {var} = {value}")
        else:
            print(f"  ⚪ {var} 未设置（将使用默认地址）")

    if not all_ok:
        print()
        print("=" * 60)
        print("❌ 环境变量检查失败")
        print()
        print("请设置以下环境变量后重试：")
        print("  export XFYUN_ASR_APP_ID='your_app_id'")
        print("  export XFYUN_ASR_ACCESS_KEY_ID='your_access_key_id'")
        print("  export XFYUN_ASR_ACCESS_KEY_SECRET='your_access_key_secret'")
        print("=" * 60)
        sys.exit(1)

    print()
    print("  ✅ 环境变量检查通过")
    print()

    # ================================================================
    # Step 2: 初始化模块
    # ================================================================
    print("━" * 60)
    print("Step 2/5: 初始化模块")
    print("━" * 60)

    # 初始化 mic_recorder
    try:
        from audio.mic_recorder import MicRecorder
        recorder = MicRecorder()
        print("  ✅ MicRecorder 初始化成功")
    except Exception as e:
        print(f"  ❌ MicRecorder 初始化失败: {e}")
        sys.exit(1)

    # 初始化 xfyun_asr_client
    try:
        from agent.xfyun_asr_client import XfyunAsrClient
        client = XfyunAsrClient()
        print("  ✅ XfyunAsrClient 初始化成功")
    except Exception as e:
        print(f"  ❌ XfyunAsrClient 初始化失败: {e}")
        sys.exit(1)

    print()

    # ================================================================
    # Step 3: 录音
    # ================================================================
    print("━" * 60)
    print("Step 3/5: 录音（5 秒）")
    print("━" * 60)
    print()
    print("  🎤 请对着小米音响麦克风说话...")
    print()
    print('  请说："自由女神像有什么历史意义？"')
    print()

    try:
        pcm_path = recorder.record(duration=5)
        print(f"  ✅ 录音完成: {pcm_path}")
    except Exception as e:
        print(f"  ❌ 录音失败: {e}")
        sys.exit(1)

    # 验证文件
    if not os.path.exists(pcm_path):
        print(f"  ❌ PCM 文件不存在: {pcm_path}")
        sys.exit(1)

    pcm_size = os.path.getsize(pcm_path)
    print(f"  📁 PCM 大小: {pcm_size} 字节 ({pcm_size / 1024:.1f} KB)")
    print()

    # ================================================================
    # Step 4: ASR 识别
    # ================================================================
    print("━" * 60)
    print("Step 4/5: ASR 识别")
    print("━" * 60)
    print()

    try:
        result = client.recognize(pcm_path)
    except Exception as e:
        print(f"  ❌ ASR 识别异常: {e}")
        sys.exit(1)

    print()

    # ================================================================
    # Step 5: 输出结果
    # ================================================================
    print("━" * 60)
    print("Step 5/5: 测试结果")
    print("━" * 60)
    print()

    if result["success"]:
        print("  ✅ ASR 识别成功")
        print()
        print("  " + "=" * 50)
        print(f"  ASR text: {result['text']}")
        print("  " + "=" * 50)
        print()

        # 检查是否匹配期望
        expected = "自由女神像有什么历史意义"
        if expected in result["text"].replace("？", "").replace("?", ""):
            print("  ✅ 识别结果与期望文本匹配！")
        else:
            print(f"  ⚠️ 识别结果与期望不完全匹配")
            print(f"     期望: {expected}")
            print(f"     实际: {result['text']}")

    else:
        print("  ❌ ASR 识别失败")
        print(f"  错误原因: {result['error']}")
        if result["text"]:
            print(f"  部分文本: {result['text']}")
        print()

    # ================================================================
    # 最终报告
    # ================================================================
    print("=" * 60)
    print("  测试报告")
    print("=" * 60)
    print()
    print(f"  环境变量:           {'✅ 通过' if all_ok else '❌ 失败'}")
    print(f"  录音文件 (WAV):     /tmp/smart_guide_question.wav")
    print(f"  PCM 文件:           {pcm_path} ({pcm_size} 字节)")
    print(f"  PCM 转换:           {'✅ 成功' if pcm_size > 0 else '❌ 失败'}")
    print(f"  讯飞 ASR 连接:      {'✅ 成功' if result['success'] else '❌ 失败'}")
    print(f"  识别文本:           {result['text'] if result['text'] else '(空)'}")
    if not result["success"]:
        print(f"  失败原因:           {result['error']}")
    print()
    print("=" * 60)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
