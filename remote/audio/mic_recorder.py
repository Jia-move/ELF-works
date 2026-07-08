"""
audio/mic_recorder.py — 麦克风录音模块

优先使用 parecord (PulseAudio) 从 Redmi USB 麦克风录音，
fallback 到 arecord -D plughw:4,0，然后用 ffmpeg 转换为 16000 Hz PCM。
用于讯飞实时语音转写大模型的音频输入。

使用方式：
    from audio.mic_recorder import MicRecorder

    recorder = MicRecorder()
    pcm_path = recorder.record(duration=5)
    # → /tmp/smart_guide_question_16k.pcm
"""

import subprocess
import sys
import os
import time

# ============================================================================
# 默认配置（当未传入 config 时使用）
# ============================================================================

# Redmi USB 麦克风
REDMI_PULSEAUDIO_SOURCE = (
    "alsa_input.usb-MV-SILICON_Redmi______________20190808-00.analog-stereo"
)
REDMI_ALSA_DEVICE = "plughw:4,0"

# 录音参数
RECORD_SAMPLE_RATE = 48000
RECORD_CHANNELS = 1
RECORD_FORMAT = "S16_LE"
DEFAULT_DURATION = 5

# 输出文件路径
WAV_OUTPUT = "/tmp/smart_guide_question.wav"
PCM_OUTPUT = "/tmp/smart_guide_question_16k.pcm"

# PCM 转码参数
PCM_SAMPLE_RATE = 16000
PCM_CHANNELS = 1

# 录音后端
BACKEND_PARECORD = "parecord"
BACKEND_ARECORD = "arecord"


# ============================================================================
# MicRecorder
# ============================================================================

class MicRecorder:
    """麦克风录音器。

    工作流程：
    1. 优先使用 parecord 从 Redmi PulseAudio source 录音 → 48000 Hz WAV
    2. Fallback: arecord -D plughw:4,0 → 48000 Hz WAV
    3. 使用 ffmpeg 转为 16000 Hz 单声道 PCM
    4. 返回 PCM 文件路径

    绝不 fallback 到 plughw:3,0（摄像头麦克风）。
    """

    def __init__(self, config: dict = None,
                 device: str = None,
                 pulseaudio_source: str = None,
                 backend: str = None,
                 wav_path: str = None,
                 pcm_path: str = None,
                 sample_rate: int = None,
                 channels: int = None):
        """
        Args:
            config:             完整配置字典（优先级最高）
            device:             ALSA 设备名（arecord 用），默认 plughw:4,0
            pulseaudio_source:  PulseAudio source 名（parecord 用）
            backend:            "parecord" | "arecord"，默认 parecord
            wav_path:           中间 WAV 文件路径
            pcm_path:           最终 PCM 文件路径
            sample_rate:        录音采样率，默认 48000
            channels:           声道数，默认 1
        """
        # ---- 从 config 读取（优先级最高）----
        ac = config.get("audio", {}) if config else {}

        # 后端选择
        if backend is not None:
            self._backend = backend
        else:
            self._backend = str(ac.get("input_backend", BACKEND_PARECORD))

        # PulseAudio source（parecord 用）
        if pulseaudio_source is not None:
            self._pa_source = pulseaudio_source
        else:
            self._pa_source = str(ac.get("input_source", REDMI_PULSEAUDIO_SOURCE))

        # ALSA 设备（arecord 用）
        if device is not None:
            self._alsa_device = device
        else:
            self._alsa_device = str(ac.get("input_device", REDMI_ALSA_DEVICE))

        # 禁止 plughw:3,0（摄像头麦克风）
        if self._alsa_device == "plughw:3,0":
            print("[mic_recorder] ⚠️ plughw:3,0 是摄像头麦克风，已自动切换到 plughw:4,0")
            self._alsa_device = REDMI_ALSA_DEVICE

        # 采样率
        if sample_rate is not None:
            self._sample_rate = sample_rate
        else:
            self._sample_rate = int(ac.get("input_rate", RECORD_SAMPLE_RATE))

        # 声道数
        if channels is not None:
            self._channels = channels
        else:
            self._channels = int(ac.get("input_channels", RECORD_CHANNELS))

        # 文件路径
        self.wav_path = wav_path or str(ac.get(
            "question_wav_path", WAV_OUTPUT,
        ))
        self.pcm_path = pcm_path or str(ac.get(
            "question_pcm_path", PCM_OUTPUT,
        ))

    # ================================================================
    # 公共接口
    # ================================================================

    def record(self, duration: int = None) -> str:
        """录音并转换为 16000 Hz PCM。

        Args:
            duration: 录音时长（秒），默认 5 秒

        Returns:
            PCM 文件路径

        Raises:
            RuntimeError: 录音或转码失败
        """
        duration = duration or DEFAULT_DURATION

        print(f"[mic_recorder] ========== 开始录音 ==========")
        print(f"[mic_recorder] 后端:     {self._backend}")
        print(f"[mic_recorder] 采样率:   {self._sample_rate} Hz")
        print(f"[mic_recorder] 声道:     {self._channels}")
        print(f"[mic_recorder] 格式:     {RECORD_FORMAT}")
        print(f"[mic_recorder] 时长:     {duration} 秒")
        print(f"[mic_recorder] WAV 输出: {self.wav_path}")
        print(f"[mic_recorder] PCM 输出: {self.pcm_path}")
        print(f"[mic_recorder] 请对着麦克风说话...")
        print()

        # Step 1: 录音 → 48000 Hz WAV
        if self._backend == BACKEND_PARECORD:
            self._record_via_parecord(duration)
        else:
            self._record_via_arecord(duration)

        # Step 2: 转码 → 16000 Hz PCM
        self._convert_to_pcm()

        # Step 3: 验证 PCM 文件
        self._verify_pcm()

        print(f"[mic_recorder] ✅ 录音完成: {self.pcm_path}")
        return self.pcm_path

    # ================================================================
    # 录音方法
    # ================================================================

    def _record_via_parecord(self, duration: int):
        """使用 parecord 从 Redmi PulseAudio source 录音到 WAV。

        优先方案：直接使用 PulseAudio source 名，不依赖 ALSA 卡号，
        卡号可能在重启后变化。
        """
        cmd = [
            "parecord",
            "--device", self._pa_source,
            "--format", "s16le",
            "--rate", str(self._sample_rate),
            "--channels", str(self._channels),
            "--file-format", "wav",
            self.wav_path,
        ]

        print(f"[mic_recorder] 设备: Redmi USB Audio")
        print(f"[mic_recorder] source: {self._pa_source}")
        print(f"[mic_recorder] 执行: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 10,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                print(f"[mic_recorder] ⚠️ parecord 失败: {stderr}")
                print(f"[mic_recorder] fallback 到 arecord...")
                self._record_via_arecord(duration)
                return
            print(f"[mic_recorder] ✅ parecord 完成")

        except subprocess.TimeoutExpired:
            print(f"[mic_recorder] ⚠️ parecord 超时，fallback 到 arecord...")
            self._record_via_arecord(duration)
        except FileNotFoundError:
            print(f"[mic_recorder] ⚠️ parecord 不可用，fallback 到 arecord...")
            self._record_via_arecord(duration)

    def _record_via_arecord(self, duration: int):
        """使用 arecord 从 ALSA 设备录音到 WAV（fallback 方案）。

        仅使用 plughw:4,0（Redmi），不 fallback 到 plughw:3,0。
        """
        # 安全检查：禁止 plughw:3,0
        if self._alsa_device == "plughw:3,0":
            raise RuntimeError(
                "plughw:3,0 是摄像头麦克风，已禁止使用。"
                "请确认 Redmi USB 音响已连接（plughw:4,0）。"
            )

        cmd = [
            "arecord",
            "-D", self._alsa_device,
            "-f", RECORD_FORMAT,
            "-r", str(self._sample_rate),
            "-c", str(self._channels),
            "-d", str(duration),
            self.wav_path,
        ]

        print(f"[mic_recorder] 设备: {self._alsa_device}")
        print(f"[mic_recorder] 执行: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 10,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise RuntimeError(
                    f"arecord 失败 (code={result.returncode}): {stderr}\n"
                    f"请确认 Redmi USB 音响已连接（{self._alsa_device}）。"
                )
            print(f"[mic_recorder] ✅ arecord 完成")

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"arecord 超时，请检查音频设备 {self._alsa_device} 是否正常"
            )
        except FileNotFoundError:
            raise RuntimeError(
                "arecord 命令不存在，请安装 alsa-utils: sudo apt install alsa-utils"
            )

    # ================================================================
    # 转码与验证
    # ================================================================

    def _convert_to_pcm(self):
        """使用 ffmpeg 将 WAV 转为 16000 Hz 单声道 PCM。"""
        if not os.path.exists(self.wav_path):
            raise RuntimeError(f"WAV 文件不存在: {self.wav_path}")

        wav_size = os.path.getsize(self.wav_path)
        print(f"[mic_recorder] WAV 文件大小: {wav_size} 字节 ({wav_size / 1024:.1f} KB)")

        cmd = [
            "ffmpeg",
            "-y",  # 覆盖已有文件
            "-i", self.wav_path,
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            self.pcm_path,
        ]

        print(f"[mic_recorder] 转码: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise RuntimeError(f"ffmpeg 转码失败 (code={result.returncode}): {stderr}")
            print(f"[mic_recorder] ✅ ffmpeg 转码完成")

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg 转码超时")
        except FileNotFoundError:
            raise RuntimeError("ffmpeg 命令不存在，请安装 ffmpeg: sudo apt install ffmpeg")

    def _verify_pcm(self):
        """验证 PCM 文件是否存在且非空。"""
        if not os.path.exists(self.pcm_path):
            raise RuntimeError(f"PCM 文件不存在: {self.pcm_path}")

        pcm_size = os.path.getsize(self.pcm_path)
        if pcm_size == 0:
            raise RuntimeError(f"PCM 文件为空: {self.pcm_path}")

        # 计算音频时长
        # PCM: 16000 Hz, 16bit (2 bytes), 1 channel
        duration = pcm_size / (PCM_SAMPLE_RATE * 2 * PCM_CHANNELS)
        print(f"[mic_recorder] PCM 文件大小: {pcm_size} 字节 ({pcm_size / 1024:.1f} KB)")
        print(f"[mic_recorder] PCM 时长:     {duration:.2f} 秒")


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    """命令行测试入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="麦克风录音 → 16000 Hz PCM（Redmi USB）"
    )
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=DEFAULT_DURATION,
        help=f"录音时长（秒），默认 {DEFAULT_DURATION}",
    )
    parser.add_argument(
        "-D", "--device",
        default=REDMI_ALSA_DEVICE,
        help=f"ALSA 设备（arecord fallback），默认 {REDMI_ALSA_DEVICE}",
    )
    parser.add_argument(
        "--backend",
        choices=[BACKEND_PARECORD, BACKEND_ARECORD],
        default=BACKEND_PARECORD,
        help=f"录音后端，默认 {BACKEND_PARECORD}",
    )
    parser.add_argument(
        "--pa-source",
        default=REDMI_PULSEAUDIO_SOURCE,
        help="PulseAudio source 名称",
    )
    args = parser.parse_args()

    try:
        recorder = MicRecorder(
            device=args.device,
            backend=args.backend,
            pulseaudio_source=args.pa_source,
        )
        pcm_path = recorder.record(duration=args.duration)
        print()
        print(f"✅ 录音成功")
        print(f"   PCM 文件: {pcm_path}")
    except RuntimeError as e:
        print(f"❌ 录音失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
