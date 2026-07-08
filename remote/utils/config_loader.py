"""
config_loader.py — 轻量级配置文件加载器

特性：
- 配置文件不存在 → 使用默认值，不崩溃
- 配置项缺失 → 该配置项使用默认值
- PyYAML 未安装 → 使用默认值 + 给出提示
- 解析失败 → 使用默认值 + 打印警告

使用方式：
    from utils.config_loader import load_config, print_config

    config = load_config("config/config.yaml")
    print_config(config)
    model_path = config["model"]["path"]
"""

import os
import copy


# ============================================================================
# 默认配置（当 config.yaml 不存在或解析失败时使用）
# ============================================================================
DEFAULTS = {
    "runtime": {
        "mode": "sum",
    },
    "modes": {
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
    },
    "model": {
        "path": "./rknnModel/best.rknn",
        "input_width": 640,
        "input_height": 640,
    },
    "camera": {
        "id": "/dev/video21",
    },
    "inference": {
        "conf_threshold": 0.25,
        "iou_threshold": 0.45,
        "thread_num": 8,
    },
    "display": {
        "width": 1420,
        "height": 800,
        "window_name": "Smart Guide Glasses",
        "show_fps": True,
        "draw_boxes": True,
    },
    "performance": {
        "print_interval_sec": 1.0,
    },
    "pipeline": {
        "async_mode": False,
        "frame_queue_size": 4,
        "result_queue_size": 2,
    },
    "event_trigger": {
        "cooldown_seconds": 5.0,
        "min_confidence": 0.3,
        "min_size": "medium",
        "important_classes": [],
        "safety_classes": [],
    },
    "agent": {
        "mode": "mock",
        "api_key_env": "GUIDE_AGENT_API_KEY",
        "timeout_seconds": 5,
        "enable_cloud": False,
    },
    "audio": {
        "enable": True,
        "mode": "mock",
        "cooldown_seconds": 8,
        # --- Redmi USB 录音 ---
        "input_backend": "parecord",
        "input_source": "alsa_input.usb-MV-SILICON_Redmi______________20190808-00.analog-stereo",
        "input_device": "plughw:4,0",
        "input_rate": 48000,
        "input_channels": 1,
        "record_seconds": 5,
        # --- Redmi USB 播报 ---
        "output_backend": "paplay",
        "output_sink": "alsa_output.usb-MV-SILICON_Redmi______________20190808-00.analog-stereo",
        "output_device": "plughw:4,0",
        # --- 临时文件 ---
        "tts_wav_path": "/tmp/smart_guide_tts.wav",
        "question_wav_path": "/tmp/smart_guide_question.wav",
        "question_pcm_path": "/tmp/smart_guide_question_16k.pcm",
    },
    "speaker": {
        "mode": "mock",
        "output_device": "plughw:4,0",
        "voice": "zh-CN-XiaoxiaoNeural",
        "max_chars": 160,
        "tts_timeout": 25,
        "fallback_to_mock": True,
    },
    "asr": {
        "enabled": True,
        "provider": "xfyun",
        "input_device": "plughw:4,0",
        "sample_rate": 16000,
        "channels": 1,
    },
    "ui": {
        "mode": "opencv",
        "enable_qt": False,
        "fallback_to_opencv": True,
    },
    "web": {
        "enable_record": True,
        "enable_api_server": False,
        "host": "0.0.0.0",
        "port": 8080,
        "record_file": "data/guide_records.jsonl",
        "device_id": "rk3588_glasses_001",
    },
    "deepseek": {
        "enabled": True,
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "timeout": 10,
        "max_retries": 1,
        "temperature": 0.3,
        "max_tokens": 300,
        "thinking": {
            "type": "disabled",
        },
    },
    "qa": {
        "enabled": True,
        "input_mode": "text_or_voice",
        "voice_enabled": True,
        "fallback_to_text": True,
        "max_history_turns": 5,
        "answer_max_chars": 120,
        "intro_max_chars": 80,
    },
    "web_upload": {
        "enabled": False,
        "base_url": "http://localhost:8000",
        "device_id": "elf2-01",
        "heartbeat_interval_sec": 10,
        "connect_timeout_sec": 2,
        "read_timeout_sec": 5,
        "queue_maxsize": 100,
        "retry_count": 3,
        "source": "rknn",
    },
}


def _check_unknown_keys(defaults: dict, user: dict, path: str = "") -> list:
    """递归检查 user 字典中是否存在 defaults 没有的键。

    Returns:
        list of warning message strings
    """
    warnings = []
    for key in user:
        full_key = f"{path}.{key}" if path else key
        if key not in defaults:
            warnings.append(f"unknown key '{full_key}' (valid: {list(defaults.keys())})")
        elif isinstance(defaults[key], dict) and isinstance(user[key], dict):
            warnings.extend(_check_unknown_keys(defaults[key], user[key], full_key))
    return warnings


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典。override 中的值覆盖 base 中的值。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载配置文件，失败时返回默认配置。

    Args:
        config_path: YAML 配置文件路径

    Returns:
        dict: 合并后的完整配置（默认值 + 用户覆盖）
    """
    config = copy.deepcopy(DEFAULTS)

    if not os.path.exists(config_path):
        print(f"[config] '{config_path}' not found, using defaults")
        return config

    try:
        import yaml
    except ImportError:
        print("[config] PyYAML not installed, using defaults")
        print("[config]   Install: pip install pyyaml")
        return config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
    except Exception as e:
        print(f"[config] Failed to read '{config_path}': {e}")
        print("[config]   Using defaults")
        return config

    if user_config is None:
        print(f"[config] '{config_path}' is empty, using defaults")
        return config

    if not isinstance(user_config, dict):
        print(f"[config] '{config_path}' is not a valid mapping, using defaults")
        return config

    try:
        config = _deep_merge(DEFAULTS, user_config)
        print(f"[config] Loaded from '{config_path}'")
    except Exception as e:
        print(f"[config] Failed to merge config: {e}, using defaults")
        return copy.deepcopy(DEFAULTS)

    # 检查用户配置中是否有未知键（可能是拼写错误）
    unknown_warnings = _check_unknown_keys(DEFAULTS, user_config)
    for w in unknown_warnings:
        print(f"[config] WARNING: {w}")

    return config


def print_config(config: dict) -> None:
    """打印当前生效的关键配置项。"""
    print("[config] --- Effective Configuration ---")
    print(f"  model.path           = {config['model']['path']}")
    print(f"  model.input          = {config['model']['input_width']}x{config['model']['input_height']}")
    print(f"  camera.id            = {config['camera']['id']}")
    print(f"  inference.conf_thr   = {config['inference']['conf_threshold']}")
    print(f"  inference.iou_thr    = {config['inference']['iou_threshold']}")
    print(f"  inference.thread_num = {config['inference']['thread_num']}")
    print(f"  display.window       = {config['display']['width']}x{config['display']['height']}")
    print(f"  display.show_fps     = {config['display']['show_fps']}")
    print(f"  display.draw_boxes   = {config['display']['draw_boxes']}")
    print(f"  perf.print_interval  = {config['performance']['print_interval_sec']}s")
    print(f"  pipeline.async_mode  = {config['pipeline']['async_mode']}")
    print(f"  pipeline.frame_q     = {config['pipeline']['frame_queue_size']}")
    print(f"  pipeline.result_q    = {config['pipeline']['result_queue_size']}")
    print(f"  trigger.cooldown     = {config['event_trigger']['cooldown_seconds']}s")
    print(f"  trigger.min_conf     = {config['event_trigger']['min_confidence']}")
    print(f"  trigger.min_size     = {config['event_trigger']['min_size']}")
    print("[config] ---------------------------------")
