"""
audio/speaker.py — 语音播报模块

提供 Speaker 类，支持 mock 播报和 edge-tts 真实播报。

使用方式：
    from audio.speaker import Speaker

    speaker = Speaker(config)
    speaker.speak("前方是故宫，值得驻足欣赏。", class_name="forbidden_city")
"""

import os
import re
import subprocess
import time
import threading


class Speaker:
    """语音播报器。

    支持两种模式：
    - mock:     终端打印 "正在播报：xxx"（默认）
    - edge_tts: 使用 Microsoft Edge TTS 生成语音 → ffmpeg 转 wav → aplay 播放
    """

    # --- 可配置默认值 ---
    _DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
    _DEFAULT_MAX_CHARS = 160
    _DEFAULT_TTS_TIMEOUT = 25
    _DEFAULT_OUTPUT_DEVICE = "plughw:4,0"  # Redmi USB

    # --- 临时文件路径 ---
    _TMP_MP3 = "/tmp/smart_guide_tts.mp3"
    _TMP_WAV = "/tmp/smart_guide_tts.wav"

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典。优先读取 speaker 节，fallback 到 audio 节。
        """
        # ---- 读取 speaker 节（新增）----
        spk = config.get("speaker", {})

        self.mode = str(spk.get("mode", "mock"))
        self.voice = str(spk.get("voice", self._DEFAULT_VOICE))
        self.max_chars = int(spk.get("max_chars", self._DEFAULT_MAX_CHARS))
        self.tts_timeout = int(spk.get("tts_timeout", self._DEFAULT_TTS_TIMEOUT))
        self.fallback_to_mock = bool(spk.get("fallback_to_mock", True))

        # output_device: speaker 节优先，否则使用 audio 节的 output_device
        if "output_device" in spk:
            self.output_device = str(spk["output_device"])
        else:
            ac = config.get("audio", {})
            self.output_device = str(ac.get("output_device", self._DEFAULT_OUTPUT_DEVICE))

        # 如果 speaker 节未设置 mode（值是默认 mock），但 audio 节设了 mode=tts/edge_tts
        if self.mode == "mock":
            ac_mode = str(config.get("audio", {}).get("mode", "mock"))
            if ac_mode in ("tts", "edge_tts"):
                self.mode = "edge_tts"

        # ---- 从 audio 节读取通用设置 ----
        ac = config.get("audio", {})
        self.enabled = bool(ac.get("enable", True))
        self.cooldown_seconds = float(ac.get("cooldown_seconds", 8))

        # TTS 临时文件路径（优先从 config 读取）
        self._TMP_MP3 = str(ac.get("tts_mp3_path", self._TMP_MP3))
        self._TMP_WAV = str(ac.get("tts_wav_path", self._TMP_WAV))

        # 播报后端优先级
        self._output_backend = str(ac.get("output_backend", "paplay"))

        # ---- 冷却追踪：{class_name: last_speak_time} ----
        self._lock = threading.Lock()
        self._cooldowns = {}

    # ================================================================
    # 公共接口
    # ================================================================

    def speak(self, text: str, class_name: str = None,
              priority: str = "normal") -> bool:
        """播报一段文本。

        Args:
            text:       播报文本内容
            class_name: 关联的类别名（用于冷却去重），如 "forbidden_city"
            priority:   优先级 "high"|"normal"（预留）

        Returns:
            True 表示已播报，False 表示跳过（冷却中或已禁用）
        """
        if not self.enabled:
            return False

        # 冷却检查
        if class_name and not self._check_cooldown(class_name):
            return False

        # 执行播报（异常不影响调用方）
        try:
            ok = False
            if self.mode == "edge_tts":
                ok = self._edge_tts_speak(text)
                if not ok and self.fallback_to_mock:
                    self._mock_speak(text)
            else:
                self._mock_speak(text)
                ok = True
        except Exception:
            # 最外层防护：任何未预期的异常都 fallback 到 mock
            if self.fallback_to_mock and self.mode != "mock":
                try:
                    self._mock_speak(text)
                except Exception:
                    pass
            return False

        # 更新冷却
        if class_name:
            self._update_cooldown(class_name)

        return ok

    # ================================================================
    # Mock 播报
    # ================================================================

    @staticmethod
    def _mock_speak(text: str):
        """Mock 播报：终端打印。"""
        display = text if len(text) <= 60 else text[:57] + "..."
        print(f"[speaker] fallback mock: {display}")

    # ================================================================
    # Edge-TTS 播报
    # ================================================================

    def _edge_tts_speak(self, text: str) -> bool:
        """使用 edge-tts → ffmpeg → aplay 管线播报。

        Returns:
            True 表示播放成功，False 表示任一步骤失败。
        """
        # ---- 1. 截断文本 ----
        text = text.strip()
        if len(text) > self.max_chars:
            text = text[:self.max_chars]
        if not text:
            return False

        display = text if len(text) <= 60 else text[:57] + "..."
        print(f"[speaker] 正在播报：{display}")

        # ---- 2. 清理旧临时文件 ----
        for p in (self._TMP_MP3, self._TMP_WAV):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

        # ---- 3. edge-tts: 文本 → mp3 ----
        if not self._run_edge_tts(text):
            return False
        print("[speaker] edge-tts ok")

        # ---- 4. ffmpeg: mp3 → wav ----
        if not self._run_ffmpeg():
            return False
        print("[speaker] ffmpeg ok")

        # ---- 5. 播放 wav（paplay → ffplay → aplay 多级回退）----
        if not self._play_wav():
            return False
        print("[speaker] 播放 ok")

        return True

    def _run_edge_tts(self, text: str) -> bool:
        """调用 edge-tts 生成 mp3 文件。"""
        cmd = [
            "edge-tts",
            "--voice", self.voice,
            "--text", text,
            "--write-media", self._TMP_MP3,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.tts_timeout,
            )
            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                print(f"[speaker] edge-tts 返回码非0: rc={proc.returncode} err={stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            print(f"[speaker] edge-tts 超时 ({self.tts_timeout}s)")
            return False
        except FileNotFoundError:
            print("[speaker] edge-tts 命令未找到，请确认已安装: pip install edge-tts")
            return False
        except Exception as e:
            print(f"[speaker] edge-tts 异常: {e}")
            return False

        # 检查输出文件
        if not os.path.exists(self._TMP_MP3):
            print("[speaker] edge-tts 未生成 mp3 文件")
            return False
        if os.path.getsize(self._TMP_MP3) == 0:
            print("[speaker] edge-tts 生成的 mp3 文件为空")
            return False

        return True

    def _run_ffmpeg(self) -> bool:
        """调用 ffmpeg 将 mp3 转为 wav。"""
        cmd = [
            "ffmpeg",
            "-y",
            "-i", self._TMP_MP3,
            "-ar", "48000",
            "-ac", "2",
            self._TMP_WAV,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                print(f"[speaker] ffmpeg 返回码非0: rc={proc.returncode} err={stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            print("[speaker] ffmpeg 超时")
            return False
        except FileNotFoundError:
            print("[speaker] ffmpeg 命令未找到")
            return False
        except Exception as e:
            print(f"[speaker] ffmpeg 异常: {e}")
            return False

        # 检查输出文件
        if not os.path.exists(self._TMP_WAV):
            print("[speaker] ffmpeg 未生成 wav 文件")
            return False
        if os.path.getsize(self._TMP_WAV) == 0:
            print("[speaker] ffmpeg 生成的 wav 文件为空")
            return False

        return True

    # ================================================================
    # 播放管线（paplay → ffplay → aplay）
    # ================================================================

    def _verify_wav(self) -> bool:
        """验证 wav 文件存在且非空，打印详细信息到日志。"""
        wav = self._TMP_WAV
        exists = os.path.exists(wav)
        size = os.path.getsize(wav) if exists else 0
        print(f"[speaker] wav 文件: {wav}")
        print(f"[speaker] wav 存在: {exists}, 大小: {size} bytes")
        if not exists:
            print("[speaker] wav 文件不存在，无法播放")
            return False
        if size == 0:
            print("[speaker] wav 文件大小为 0，无法播放")
            return False
        return True

    @staticmethod
    def _get_default_sink() -> str:
        """获取当前 PulseAudio Default Sink 名称。"""
        try:
            proc = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass
        return "未知"

    @staticmethod
    def _ensure_redmi_sink():
        """播放前确保 Default Sink 是 Redmi USB 音响。

        从 audio_init 模块调用，避免重复检测逻辑。
        如果当前 sink 不是 Redmi，自动切换。
        """
        try:
            from audio.audio_init import ensure_redmi_sink_for_playback
            ok = ensure_redmi_sink_for_playback()
            if ok:
                print("[speaker] ✅ Redmi sink ready")
            else:
                print("[speaker] ⚠️ Redmi sink 未就绪，播放可能输出到其他设备")
        except ImportError:
            # audio_init 模块不可用时，手动检查
            print("[speaker] ⚠️ audio_init 模块不可用，跳过 sink 检查")

    @staticmethod
    def _detect_usb_card() -> str:
        """动态检测 USB Audio 声卡号，返回 plughw:X,0 或空字符串。"""
        try:
            proc = subprocess.run(
                ["aplay", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            output = proc.stdout + proc.stderr
            for line in output.splitlines():
                if "USB Audio" in line:
                    # 行格式: "card X: ..."
                    m = re.search(r"card\s+(\d+)", line)
                    if m:
                        card = m.group(1)
                        return f"plughw:{card},0"
        except Exception:
            pass
        return ""

    def _play_wav(self) -> bool:
        """多级回退播放 wav 文件。

        优先级：
          1. paplay（直接 PulseAudio 播放，通过 Redmi sink）
          2. ffplay -nodisp -autoexit -loglevel error
          3. aplay -D plughw:4,0（Redmi，最后手段）
        """
        # ---- 播放前校验 ----
        if not self._verify_wav():
            return False

        # ---- 确保 Default Sink 是 Redmi ----
        self._ensure_redmi_sink()

        default_sink = self._get_default_sink()
        print(f"[speaker] Default Sink: {default_sink}")

        # ---- 方法 1: paplay ----
        if self._try_paplay():
            return True

        # ---- 方法 2: ffplay ----
        if self._try_ffplay():
            return True

        # ---- 方法 3: aplay（动态检测 USB 声卡）----
        if self._try_aplay():
            return True

        return False

    def _try_paplay(self) -> bool:
        """使用 paplay 通过 PulseAudio 播放 wav。"""
        cmd = ["paplay", self._TMP_WAV]
        print(f"[speaker] 播放命令: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                print(f"[speaker] paplay 成功 (rc=0)")
                return True
            stderr = (proc.stderr or "").strip()
            print(f"[speaker] paplay 返回码非0: rc={proc.returncode} err={stderr[:200]}")
            return False
        except FileNotFoundError:
            print("[speaker] paplay 命令未找到，跳过")
            return False
        except subprocess.TimeoutExpired:
            print("[speaker] paplay 超时")
            return False
        except Exception as e:
            print(f"[speaker] paplay 异常: {e}")
            return False

    def _try_ffplay(self) -> bool:
        """使用 ffplay 播放 wav（无需显示窗口）。"""
        cmd = [
            "ffplay", "-nodisp", "-autoexit",
            "-loglevel", "error",
            self._TMP_WAV,
        ]
        print(f"[speaker] 播放命令: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                print(f"[speaker] ffplay 成功 (rc=0)")
                return True
            stderr = (proc.stderr or "").strip()
            print(f"[speaker] ffplay 返回码非0: rc={proc.returncode} err={stderr[:200]}")
            return False
        except FileNotFoundError:
            print("[speaker] ffplay 命令未找到，跳过")
            return False
        except subprocess.TimeoutExpired:
            print("[speaker] ffplay 超时")
            return False
        except Exception as e:
            print(f"[speaker] ffplay 异常: {e}")
            return False

    def _try_aplay(self) -> bool:
        """使用 aplay 播放 wav（最后手段）。

        仅使用 Redmi 设备 plughw:4,0 或动态检测到的 USB 声卡。
        不使用 plughw:3,0（摄像头麦克风的声卡输出）。
        """
        # 确定 aplay 设备
        device = self._detect_usb_card()
        if not device:
            device = "plughw:4,0"
        # 如果配置的设备是 Redmi 兼容设备，使用配置值
        if self.output_device and self.output_device != "plughw:3,0":
            if device != self.output_device:
                device = self.output_device

        cmd = ["aplay", "-D", device, self._TMP_WAV]
        print(f"[speaker] 播放命令: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                print(f"[speaker] aplay 成功 (rc=0, device={device})")
                return True
            stderr = (proc.stderr or "").strip()
            print(f"[speaker] aplay 返回码非0: rc={proc.returncode} device={device} err={stderr[:200]}")
            return False
        except FileNotFoundError:
            print("[speaker] aplay 命令未找到，请安装 alsa-utils")
            return False
        except subprocess.TimeoutExpired:
            print("[speaker] aplay 超时")
            return False
        except Exception as e:
            print(f"[speaker] aplay 异常: {e}")
            return False

    # ================================================================
    # 冷却管理
    # ================================================================

    def _check_cooldown(self, class_name: str) -> bool:
        """检查该类是否已过冷却期。"""
        with self._lock:
            last = self._cooldowns.get(class_name, 0)
            return (time.time() - last) >= self.cooldown_seconds

    def _update_cooldown(self, class_name: str):
        """更新该类的最后播报时间。"""
        with self._lock:
            self._cooldowns[class_name] = time.time()

    def reset_cooldowns(self):
        """重置所有冷却计时（用于测试）。"""
        with self._lock:
            self._cooldowns.clear()
