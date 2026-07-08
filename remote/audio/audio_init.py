"""
audio/audio_init.py — Redmi USB 音频设备自检与初始化

在程序启动时确保 PulseAudio 默认输入/输出都指向 Redmi USB 设备。
语音问答 (/voice) 前也会调用以确保录音和播报设备正确。

使用方式：
    from audio.audio_init import ensure_redmi_audio

    result = ensure_redmi_audio()
    if not result["ready"]:
        print("Redmi 音频设备未就绪，语音功能不可用")
"""

import subprocess
import sys
import os
import threading

# ============================================================================
# Redmi USB 设备标识（来自 pactl list short sinks/sources）
# ============================================================================

REDMI_SINK_NAME = (
    "alsa_output.usb-MV-SILICON_Redmi______________20190808-00.analog-stereo"
)
REDMI_SOURCE_NAME = (
    "alsa_input.usb-MV-SILICON_Redmi______________20190808-00.analog-stereo"
)

# 用于模糊匹配的关键词（不区分大小写）
REDMI_KEYWORDS = ["Redmi", "MV-SILICON"]

# 全局状态（避免重复初始化）
_lock = threading.Lock()
_initialized = False
_last_result = None


# ============================================================================
# 内部查找函数
# ============================================================================

def _find_pactl_device(list_cmd: list, keywords: list, exact_name: str) -> str:
    """在 pactl list 输出中查找匹配 Redmi 的设备名。

    优先精确匹配 exact_name，其次模糊匹配 keywords。

    Args:
        list_cmd:   如 ["pactl", "list", "short", "sinks"]
        keywords:   模糊匹配关键词列表
        exact_name: 精确匹配的设备全名

    Returns:
        设备名称字符串，未找到返回 None
    """
    try:
        proc = subprocess.run(
            list_cmd,
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None

    output = proc.stdout + proc.stderr

    # 优先精确匹配
    for line in output.splitlines():
        if exact_name in line:
            return exact_name

    # 模糊匹配
    for line in output.splitlines():
        lower = line.lower()
        if any(kw.lower() in lower for kw in keywords):
            parts = line.split()
            # pactl list short 格式: <index>\t<name>\t<driver>\t<sample>\t<state>
            if len(parts) >= 2:
                return parts[1]

    return None


def _find_redmi_sink() -> str:
    """查找 Redmi USB 音频输出设备（sink）。"""
    return _find_pactl_device(
        ["pactl", "list", "short", "sinks"],
        REDMI_KEYWORDS,
        REDMI_SINK_NAME,
    )


def _find_redmi_source() -> str:
    """查找 Redmi USB 音频输入设备（source）。"""
    return _find_pactl_device(
        ["pactl", "list", "short", "sources"],
        REDMI_KEYWORDS,
        REDMI_SOURCE_NAME,
    )


def _get_current_default_sink() -> str:
    """获取当前 PulseAudio 默认 sink。"""
    try:
        proc = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return ""


def _get_current_default_source() -> str:
    """获取当前 PulseAudio 默认 source。"""
    try:
        proc = subprocess.run(
            ["pactl", "get-default-source"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return ""


# ============================================================================
# 主初始化函数
# ============================================================================

def ensure_redmi_audio(force: bool = True, quiet: bool = False) -> dict:
    """确保 Redmi USB 音频设备就绪。

    执行步骤：
    1. 检查 pactl 是否可用（PulseAudio 是否运行）
    2. 查找 Redmi sink（播放输出）
    3. 查找 Redmi source（录音输入）
    4. 将默认 sink/source 设置为 Redmi
    5. 打印诊断信息

    Args:
        force: True=强制执行 pactl set-default-sink/source
        quiet: True=减少日志输出

    Returns:
        {
            "ready":   bool,   # 设备就绪（sink 和 source 都找到）
            "sink":    str,    # Redmi sink 名称（或 None）
            "source":  str,    # Redmi source 名称（或 None）
            "errors":  [str],  # 错误信息列表
        }
    """
    global _initialized, _last_result

    with _lock:
        # 如果已经初始化过且不强制，返回缓存结果
        if _initialized and not force:
            return _last_result

        result = {
            "ready": False,
            "sink": None,
            "source": None,
            "errors": [],
        }

        if not quiet:
            print("[audio] ====== Redmi USB 音频设备自检 ======")

        # ---- Step 1: 检查 pactl ----
        try:
            subprocess.run(
                ["pactl", "--version"],
                capture_output=True, text=True, timeout=3,
                check=False,
            )
        except FileNotFoundError:
            msg = "pactl 不可用，PulseAudio 可能未运行"
            result["errors"].append(msg)
            print(f"[audio] ❌ {msg}")
            _last_result = result
            return result
        except Exception as e:
            msg = f"pactl 异常: {e}"
            result["errors"].append(msg)
            print(f"[audio] ❌ {msg}")
            _last_result = result
            return result

        # ---- Step 2: 查找 Redmi sink ----
        sink = _find_redmi_sink()
        result["sink"] = sink
        if not quiet:
            print(f"[audio] Redmi output sink found: {sink is not None}")

        if not sink:
            msg = "未找到 Redmi USB 音频输出设备（sink），请确认音响已连接"
            result["errors"].append(msg)
        elif not quiet and sink:
            print(f"[audio]   sink: {sink}")

        # ---- Step 3: 查找 Redmi source ----
        source = _find_redmi_source()
        result["source"] = source
        if not quiet:
            print(f"[audio] Redmi input source found: {source is not None}")

        if not source:
            msg = "未找到 Redmi USB 音频输入设备（source），请确认麦克风已连接"
            result["errors"].append(msg)
        elif not quiet and source:
            print(f"[audio]   source: {source}")

        # ---- Step 4: 设置默认 sink ----
        if sink and force:
            current_sink = _get_current_default_sink()
            if current_sink != sink:
                try:
                    subprocess.run(
                        ["pactl", "set-default-sink", sink],
                        capture_output=True, text=True, timeout=5, check=True,
                    )
                    if not quiet:
                        print(f"[audio] Default Sink: {sink} (was: {current_sink or 'none'})")
                except Exception as e:
                    msg = f"设置 Default Sink 失败: {e}"
                    result["errors"].append(msg)
                    print(f"[audio] ❌ {msg}")
            else:
                if not quiet:
                    print(f"[audio] Default Sink: {sink} (unchanged)")

        # ---- Step 5: 设置默认 source ----
        if source and force:
            current_source = _get_current_default_source()
            if current_source != source:
                try:
                    subprocess.run(
                        ["pactl", "set-default-source", source],
                        capture_output=True, text=True, timeout=5, check=True,
                    )
                    if not quiet:
                        print(f"[audio] Default Source: {source} (was: {current_source or 'none'})")
                except Exception as e:
                    msg = f"设置 Default Source 失败: {e}"
                    result["errors"].append(msg)
                    print(f"[audio] ❌ {msg}")
            else:
                if not quiet:
                    print(f"[audio] Default Source: {source} (unchanged)")

        # ---- Step 6: 结论 ----
        if not result["errors"]:
            result["ready"] = True
            if not quiet:
                print("[audio] ✅ audio device ready")
        else:
            for err in result["errors"]:
                print(f"[audio] ❌ {err}")
            if sink and source:
                print("[audio] ⚠️ Redmi 设备存在但部分设置失败，语音功能可能仍可用")

        _initialized = True
        _last_result = result
        return result


def ensure_redmi_sink_for_playback() -> bool:
    """播放前快速检查：确保当前 Default Sink 是 Redmi。

    如果当前 sink 不对，自动切换到 Redmi。

    Returns:
        True 表示 Redmi sink 就绪，False 表示不可用
    """
    result = ensure_redmi_audio(force=True, quiet=True)
    if not result["ready"] and not result["sink"]:
        # sink 不存在，无法播放
        return False

    # 快速检查当前 sink
    current = _get_current_default_sink()

    if current == result["sink"]:
        return True

    if result["sink"]:
        try:
            subprocess.run(
                ["pactl", "set-default-sink", result["sink"]],
                capture_output=True, text=True, timeout=5, check=True,
            )
            print(f"[audio] switched Default Sink to: {result['sink']}")
            return True
        except Exception as e:
            print(f"[audio] ⚠️ 切换 Sink 失败: {e}")
            return False

    return False


def is_audio_ready() -> bool:
    """快速查询：Redmi 音频设备是否就绪（不强制设置）。"""
    result = ensure_redmi_audio(force=False, quiet=True)
    return result.get("ready", False)


def reset_audio_init():
    """重置初始化状态（用于测试）。"""
    global _initialized, _last_result
    with _lock:
        _initialized = False
        _last_result = None


# ============================================================================
# 命令行入口（调试用）
# ============================================================================

def main():
    """命令行自检入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Redmi USB 音频设备自检与初始化"
    )
    parser.add_argument(
        "--no-force", action="store_true",
        help="仅检查，不设置默认设备",
    )
    args = parser.parse_args()

    result = ensure_redmi_audio(force=not args.no_force)

    print()
    if result["ready"]:
        print("✅ Redmi 音频设备就绪")
        sys.exit(0)
    else:
        print("❌ Redmi 音频设备未就绪")
        for err in result.get("errors", []):
            print(f"   {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
