"""Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


# ========== 统一响应 ==========

class ApiResponse(BaseModel):
    status: str = "success"
    code: int = 200
    message: str = "OK"
    data: Any = None


class ErrorResponse(BaseModel):
    status: str = "error"
    code: int
    message: str
    data: Any = None


# ========== 设备 ==========

class DeviceHeartbeat(BaseModel):
    """设备心跳请求 — 不再接受 status 字段，在线由服务端判定"""
    device_id: str = Field(..., min_length=1, max_length=64)
    sent_at: Optional[datetime] = None
    software_version: Optional[str] = None
    model_name: Optional[str] = None
    mode: Optional[str] = None
    camera_status: Optional[str] = None
    npu_status: Optional[str] = None
    qt_status: Optional[str] = None
    qa_status: Optional[str] = None
    asr_status: Optional[str] = None


class DeviceOut(BaseModel):
    id: int
    name: str
    platform: str = ""
    online_status: str = "offline"  # 服务端动态计算，非设备自报
    last_seen: Optional[datetime] = None
    model_name: Optional[str] = ""
    model_display_name: Optional[str] = ""  # 前端展示用的友好名称（如 YOLOv8）
    software_version: Optional[str] = ""
    mode: Optional[str] = "unknown"
    camera_status: Optional[str] = "unknown"
    npu_status: Optional[str] = "unknown"
    qt_status: Optional[str] = "unknown"
    qa_status: Optional[str] = "unknown"
    asr_status: Optional[str] = "unknown"
    is_demo: bool = False
    first_seen: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HeartbeatResponse(BaseModel):
    server_time: datetime
    device_id: str
    online_status: str


# ========== 景点 ==========

class ScenicSpotCreate(BaseModel):
    class_name: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)
    domain: Optional[str] = "scenic"
    introduction: Optional[str] = ""
    history: Optional[str] = ""
    features: Optional[str] = ""
    narration: Optional[str] = ""
    image_url: Optional[str] = ""


class ScenicSpotUpdate(BaseModel):
    class_name: Optional[str] = Field(None, max_length=200)
    display_name: Optional[str] = Field(None, max_length=200)
    domain: Optional[str] = None
    introduction: Optional[str] = None
    history: Optional[str] = None
    features: Optional[str] = None
    narration: Optional[str] = None
    image_url: Optional[str] = None


class ScenicSpotOut(BaseModel):
    id: int
    class_name: str
    display_name: str
    domain: str = "scenic"
    introduction: str
    history: str
    features: str
    narration: str
    image_url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 识别事件 ==========

class RecognitionEventCreate(BaseModel):
    event_id: Optional[str] = Field(None, max_length=64)
    device_id: str = Field(..., min_length=1, max_length=64)
    captured_at: datetime  # API 使用 captured_at，内部映射到 DB 列 timestamp
    class_name: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=200)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fps: float = Field(default=0.0, ge=0.0)
    inference_ms: float = Field(default=0.0, ge=0.0)
    postprocess_ms: float = Field(default=0.0, ge=0.0)
    narration_triggered: bool = False
    source: str = Field(default="rknn", max_length=20)


class RecognitionEventOut(BaseModel):
    id: int
    event_id: Optional[str] = None
    device_id: str
    timestamp: datetime  # 保持字段名兼容前端
    class_name: str
    display_name: str
    confidence: float
    fps: float
    inference_ms: float
    postprocess_ms: float
    narration_triggered: bool
    source: str

    class Config:
        from_attributes = True


# ========== 问答记录 ==========

class QARecordCreate(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    scenic_name: str = Field(default="", max_length=200)
    question: str = Field(..., min_length=1)
    answer: str = ""
    provider: str = Field(default="local", max_length=50)


class QARecordOut(BaseModel):
    id: int
    device_id: str
    scenic_name: str
    question: str
    answer: str
    provider: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== Dashboard ==========

class DashboardSummary(BaseModel):
    total_devices: int = 0
    online_devices: int = 0
    total_recognitions: int = 0
    total_qa_records: int = 0
    current_scenic_spot: Optional[dict] = None
    recent_recognitions: list = []
