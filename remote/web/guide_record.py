"""
web/guide_record.py — 导览记录管理

将每次触发的导览事件写入本地 JSONL 文件。
提供追加、读取、构建记录的接口。

使用方式：
    from web.guide_record import GuideRecorder

    recorder = GuideRecorder(config)
    recorder.append(record_dict)
"""

import json
import os
import threading
from datetime import datetime


class GuideRecorder:
    """导览事件记录器。

    将导览事件追加写入 JSONL 文件。
    线程安全，写入失败不影响主流程。
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 完整配置字典，读取 web 节
        """
        wc = config.get("web", {})
        self.enabled = bool(wc.get("enable_record", True))
        self._record_path = wc.get("record_file", "data/guide_records.jsonl")
        self._device_id = wc.get("device_id", "rk3588_glasses_001")
        self._lock = threading.Lock()

    # ================================================================
    # 公共接口
    # ================================================================

    def append(self, record: dict) -> bool:
        """追加一条导览记录。

        Args:
            record: 导览事件 dict（不含 timestamp 和 device_id 时会自动补充）

        Returns:
            True 表示写入成功，False 表示已禁用或写入失败
        """
        if not self.enabled:
            return False

        # 补充字段
        if "timestamp" not in record:
            record["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "device_id" not in record:
            record["device_id"] = self._device_id

        try:
            with self._lock:
                # 确保目录存在
                dirname = os.path.dirname(self._record_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                with open(self._record_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return True
        except Exception as e:
            print(f"[web] WARNING: Failed to write record: {e}")
            return False

    def load_records(self, limit: int = 100) -> list:
        """读取最近的导览记录。

        Args:
            limit: 最大返回条数

        Returns:
            list of dict，按时间倒序
        """
        records = []
        try:
            if not os.path.exists(self._record_path):
                return records
            with open(self._record_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            # 倒序取最近
            records.reverse()
            return records[:limit]
        except Exception as e:
            print(f"[web] WARNING: Failed to load records: {e}")
            return []

    @property
    def record_count(self) -> int:
        """当前记录总数（快速估算，不精确）。"""
        try:
            if not os.path.exists(self._record_path):
                return 0
            with open(self._record_path, "r") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    # ================================================================
    # 构建记录
    # ================================================================

    @staticmethod
    def build_record(domain: str = "",
                     class_name: str = "",
                     display_name: str = "",
                     confidence: float = 0.0,
                     guide_text: str = "",
                     tts_played: bool = False) -> dict:
        """构建标准记录 dict。

        Args:
            domain:       类别域，如 "landmark"
            class_name:   标准化类别名，如 "forbidden_city"
            display_name: 中文展示名，如 "故宫"
            confidence:   置信度
            guide_text:   讲解文本
            tts_played:   是否已语音播报

        Returns:
            标准记录 dict
        """
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "domain": domain,
            "class_name": class_name,
            "display_name": display_name,
            "confidence": round(float(confidence), 4),
            "guide_text": guide_text,
            "tts_played": tts_played,
        }
