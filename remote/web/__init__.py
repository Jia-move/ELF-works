# web package — Web 接口模块
#
# guide_record.py      — 导览记录管理（本地 JSONL）
# simple_api_server.py — 轻量 HTTP API（stdlib）
# web_uploader.py      — 非阻塞 Web 上传器（事件 + 心跳 → PC 后端）

from web.guide_record import GuideRecorder  # noqa: F401
from web.web_uploader import WebUploader    # noqa: F401
