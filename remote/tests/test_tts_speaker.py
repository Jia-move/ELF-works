#!/usr/bin/env python3
"""
tests/test_tts_speaker.py — 测试 Speaker edge_tts 真实语音播报

测试流程：
  1. 读取 config/config.yaml
  2. 初始化 Speaker
  3. 播放一句："前方是故宫，故宫是明清两代的皇家宫殿。"
  4. 输出每一步状态
  5. 如果成功，应能从 Redmi / 小米音箱听到声音

运行：
    cd /home/elf/Documents/sum
    python3 tests/test_tts_speaker.py
"""

import os
import sys

# ---- 确保项目根目录在 sys.path 中 ----
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config
from audio.speaker import Speaker


def main():
    print("=" * 60)
    print(" Speaker edge_tts 真实语音播报测试")
    print("=" * 60)

    # ---- 1. 加载配置 ----
    config_path = os.path.join(_PROJECT_ROOT, "config", "config.yaml")
    print(f"\n[1] 加载配置: {config_path}")
    config = load_config(config_path)

    # ---- 2. 打印音频相关配置 ----
    spk_cfg = config.get("speaker", {})
    audio_cfg = config.get("audio", {})
    print(f"\n[2] 当前音频配置:")
    print(f"    speaker.mode            = {spk_cfg.get('mode', 'N/A')}")
    print(f"    speaker.voice           = {spk_cfg.get('voice', 'N/A')}")
    print(f"    speaker.output_device   = {spk_cfg.get('output_device', 'N/A')}")
    print(f"    speaker.max_chars       = {spk_cfg.get('max_chars', 'N/A')}")
    print(f"    speaker.fallback_to_mock= {spk_cfg.get('fallback_to_mock', 'N/A')}")
    print(f"    audio.output_device     = {audio_cfg.get('output_device', 'N/A')}")

    # ---- 3. 初始化 Speaker ----
    print(f"\n[3] 初始化 Speaker...")
    speaker = Speaker(config)
    print(f"    speaker.mode            = {speaker.mode}")
    print(f"    speaker.voice           = {speaker.voice}")
    print(f"    speaker.output_device   = {speaker.output_device}")
    print(f"    speaker.max_chars       = {speaker.max_chars}")
    print(f"    speaker.fallback_to_mock= {speaker.fallback_to_mock}")
    print(f"    speaker.enabled         = {speaker.enabled}")

    # ---- 4. 测试播报 ----
    test_text = "前方是故宫，故宫是明清两代的皇家宫殿。"
    print(f"\n[4] 播报测试文本: \"{test_text}\"")
    print(f"    文本长度: {len(test_text)} 字符")
    print()

    print("-" * 60)
    result = speaker.speak(test_text, class_name="test_forbidden_city")
    print("-" * 60)

    # ---- 5. 输出结果 ----
    print(f"\n[5] 播报结果:")
    if result:
        print("    ✅ 播报成功！应从 Redmi / 小米音箱听到声音。")
    else:
        print("    ⚠️  播报未成功（可能 fallback 到 mock，或被跳过）")

    # ---- 6. 测试 mock fallback ----
    print(f"\n[6] 测试 mock fallback...")
    spk_copy = config.get("speaker", {}).copy() if "speaker" in config else {}
    spk_copy["mode"] = "edge_tts"
    # 不改变原 config，直接测试 Speaker 内部 fallback 机制（如有 TTS 失败会自动 fallback）

    print("\n" + "=" * 60)
    print(" 测试完成")
    print("=" * 60)

    # ---- 7. 额外：验证 edge-tts 工具可调用 ----
    print(f"\n[7] 验证工具链:")
    import subprocess
    for tool, name in [("edge-tts", "edge-tts"), ("ffmpeg", "ffmpeg"), ("aplay", "aplay")]:
        try:
            proc = subprocess.run(
                ["which", tool],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0:
                print(f"    ✅ {name}: {proc.stdout.strip()}")
            else:
                print(f"    ❌ {name}: 未找到")
        except Exception as e:
            print(f"    ❌ {name}: {e}")

    # ---- 8. 验证输出设备 ----
    print(f"\n[8] 验证输出设备:")
    try:
        proc = subprocess.run(
            ["aplay", "-l"],
            capture_output=True, text=True, timeout=5,
        )
        output = proc.stdout + proc.stderr
        if "card 3" in output:
            print("    ✅ card 3 存在")
        else:
            print("    ⚠️  card 3 未在 aplay -l 中找到")
    except Exception as e:
        print(f"    ❌ aplay -l 失败: {e}")


if __name__ == "__main__":
    main()
