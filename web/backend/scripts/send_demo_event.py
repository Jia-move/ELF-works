#!/usr/bin/env python3
"""向本地 Web 服务发送一条随机景点识别事件。

用法:
    cd backend
    py scripts/send_demo_event.py
"""
import json
import random
import urllib.request
from datetime import datetime, timezone, timedelta

API_URL = "http://127.0.0.1:8000/api/device/events"

SCENIC_SPOTS = [
    {
        "class_name": "The Statue of Liberty",
        "display_name": "自由女神像",
    },
    {
        "class_name": "Oriental Pearl Tower",
        "display_name": "东方明珠塔",
    },
    {
        "class_name": "Sydney Opera House",
        "display_name": "悉尼歌剧院",
    },
    {
        "class_name": "The Sphinx",
        "display_name": "狮身人面像",
    },
    {
        "class_name": "The Great Wall",
        "display_name": "长城",
    },
]


def send_random_event():
    spot = random.choice(SCENIC_SPOTS)
    tz = timezone(timedelta(hours=8))  # UTC+8
    now = datetime.now(tz)
    event_id = f"demo-{now.strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
    payload = {
        "event_id": event_id,
        "device_id": "elf2-01",
        "captured_at": now.isoformat(),
        "class_name": spot["class_name"],
        "display_name": spot["display_name"],
        "confidence": round(random.uniform(0.85, 0.99), 4),
        "fps": round(random.uniform(2.5, 3.5), 1),
        "inference_ms": round(random.uniform(23.0, 30.0), 1),
        "postprocess_ms": round(random.uniform(18.0, 25.0), 1),
        "narration_triggered": random.choice([True, False]),
        "source": "demo",
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] {result.get('message', '')}")
            print(f"  景点: {spot['display_name']}")
            print(f"  置信度: {payload['confidence']}")
            print(f"  讲解触发: {payload['narration_triggered']}")
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}")
        print("请确认后端已启动: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")


if __name__ == "__main__":
    send_random_event()
