#!/usr/bin/env python3
"""
本地麦克风录音最小测试脚本
============================
功能：
  1. 录音 5 秒
  2. 保存为 /tmp/demo_mic.wav
  3. 打印采样率、声道、文件大小
  4. 失败时输出错误
  5. 不接入主程序

用途：验证 RK3588 远程端本地麦克风（NAU8822）是否正常工作。

运行：
  python3 tests/test_local_mic_record.py
"""

import subprocess
import sys
import os
import wave
import audioop

RECORD_SECONDS = 5
OUTPUT_FILE = "/tmp/demo_mic.wav"
# ALSA 设备：NAU8822 板载麦克风
ALSA_DEVICE = "plughw:1,0"
# 录音参数（16kHz 单声道，适合 ASR）
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_FORMAT = "S16_LE"


def record_audio() -> bool:
    """使用 arecord 录音，返回是否成功"""
    cmd = [
        "arecord",
        "-D", ALSA_DEVICE,
        "-f", SAMPLE_FORMAT,
        "-r", str(SAMPLE_RATE),
        "-c", str(CHANNELS),
        "-d", str(RECORD_SECONDS),
        OUTPUT_FILE,
    ]
    print(f"[录音] 设备: {ALSA_DEVICE}, {SAMPLE_RATE}Hz, {CHANNELS}声道, {RECORD_SECONDS}秒")
    print(f"[录音] 请对着麦克风说话...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=RECORD_SECONDS + 10)
        if result.returncode != 0:
            print(f"[录音] ❌ arecord 失败: {result.stderr.strip()}")
            return False
        print(f"[录音] ✅ arecord 完成")
        return True
    except subprocess.TimeoutExpired:
        print("[录音] ❌ arecord 超时")
        return False
    except FileNotFoundError:
        print("[录音] ❌ arecord 命令不存在，请安装 alsa-utils")
        return False


def analyze_audio() -> bool:
    """分析录音文件，打印信息，返回是否有效"""
    if not os.path.exists(OUTPUT_FILE):
        print(f"[分析] ❌ 文件不存在: {OUTPUT_FILE}")
        return False

    file_size = os.path.getsize(OUTPUT_FILE)
    print(f"[分析] 文件路径: {OUTPUT_FILE}")
    print(f"[分析] 文件大小: {file_size} 字节 ({file_size / 1024:.1f} KB)")

    try:
        with wave.open(OUTPUT_FILE, "rb") as w:
            framerate = w.getframerate()
            nchannels = w.getnchannels()
            sampwidth = w.getsampwidth()
            nframes = w.getnframes()
            duration = nframes / framerate if framerate > 0 else 0
            data = w.readframes(nframes)

            rms = audioop.rms(data, sampwidth)
            peak = audioop.max(data, sampwidth)
            max_val = (2 ** (sampwidth * 8 - 1)) - 1
            peak_pct = peak / max_val * 100 if max_val > 0 else 0

            print(f"[分析] 采样率: {framerate} Hz")
            print(f"[分析] 声道数: {nchannels}")
            print(f"[分析] 位深: {sampwidth * 8} bit")
            print(f"[分析] 帧数: {nframes}")
            print(f"[分析] 时长: {duration:.2f} 秒")
            print(f"[分析] RMS: {rms}")
            print(f"[分析] PEAK: {peak} ({peak_pct:.1f}% of max)")

            # 判断音频是否有效
            if rms < 100:
                print(f"[分析] ⚠️ 音量过低（RMS={rms}），可能未录到声音")
                return False
            elif peak >= max_val:
                print(f"[分析] ⚠️ 削顶（PEAK={peak}），增益过高")
                return True  # 仍然有效，但需调整
            else:
                print(f"[分析] ✅ 音频信号正常")
                return True

    except wave.Error as e:
        print(f"[分析] ❌ WAV 文件解析失败: {e}")
        return False
    except Exception as e:
        print(f"[分析] ❌ 未知错误: {e}")
        return False


def main():
    print("=" * 50)
    print("  本地麦克风录音测试")
    print("=" * 50)
    print()

    # 1. 录音
    if not record_audio():
        print()
        print("结论: ❌ 录音失败，请检查麦克风连接和 ALSA 设备")
        sys.exit(1)

    print()

    # 2. 分析
    if not analyze_audio():
        print()
        print("结论: ❌ 音频无效，请检查麦克风增益和连接")
        sys.exit(1)

    print()
    print("结论: ✅ 本地麦克风录音测试通过")
    print(f"      设备: {ALSA_DEVICE}")
    print(f"      文件: {OUTPUT_FILE}")
    print(f"      参数: {SAMPLE_RATE}Hz / {CHANNELS}声道 / {SAMPLE_FORMAT}")
    print()
    print("建议: 可在此脚本基础上接入 ASR 引擎")


if __name__ == "__main__":
    main()
