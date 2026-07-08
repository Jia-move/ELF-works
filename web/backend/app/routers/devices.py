"""设备管理"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Device
from app.schemas import ApiResponse, DeviceHeartbeat, DeviceOut

router = APIRouter(tags=["devices"])

# 在线超时阈值（秒）
ONLINE_TIMEOUT_SECONDS = 30


def compute_online_status(device: Device) -> str:
    """服务端动态计算设备在线状态。

    基于 last_seen（服务器接收时间）与当前 UTC 时间的差值：
      - <= ONLINE_TIMEOUT_SECONDS → "online"
      - >  ONLINE_TIMEOUT_SECONDS  → "offline"
      - last_seen 为 None          → "offline"
    """
    if device.last_seen is None:
        return "offline"
    now = datetime.now(timezone.utc)
    # 处理 naive datetime（历史数据可能没有时区）
    last = device.last_seen
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = now - last
    return "online" if delta.total_seconds() <= ONLINE_TIMEOUT_SECONDS else "offline"


def _apply_device_heartbeat(device: Device, req: DeviceHeartbeat):
    """将心跳请求中的字段同步到设备记录（不覆盖 last_seen）"""
    if req.sent_at is not None:
        device.sent_at = req.sent_at
    if req.software_version is not None:
        device.software_version = req.software_version
    if req.model_name is not None:
        device.model_name = req.model_name
    if req.mode is not None:
        device.mode = req.mode
    if req.camera_status is not None:
        device.camera_status = req.camera_status
    if req.npu_status is not None:
        device.npu_status = req.npu_status
    if req.qt_status is not None:
        device.qt_status = req.qt_status
    if req.qa_status is not None:
        device.qa_status = req.qa_status
    if req.asr_status is not None:
        device.asr_status = req.asr_status


# 模型文件名 → 前端展示名称的映射表
_MODEL_DISPLAY_NAME_MAP = {
    "best.rknn": "YOLOv8",
}


def _resolve_model_display_name(model_name: Optional[str]) -> str:
    """将内部模型名称（如 best.rknn）映射为前端展示用的友好名称。

    真实模型文件路径不受影响；此函数仅影响 Web 页面上的显示文本。
    """
    if not model_name:
        return ""
    return _MODEL_DISPLAY_NAME_MAP.get(model_name, model_name)


def _device_to_out(device: Device) -> dict:
    """将 DB 模型转为 API 响应，包含动态 online_status 和 model_display_name"""
    data = DeviceOut.model_validate(device).model_dump()
    data["online_status"] = compute_online_status(device)
    data["model_display_name"] = _resolve_model_display_name(device.model_name)
    return data


@router.get("/api/devices", response_model=ApiResponse)
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.id).all()
    return ApiResponse(
        status="success",
        code=200,
        message="OK",
        data={"list": [_device_to_out(d) for d in devices]},
    )


@router.post("/api/devices/heartbeat", response_model=ApiResponse)
def device_heartbeat(req: DeviceHeartbeat, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    device = db.query(Device).filter(Device.name == req.device_id).first()

    if device:
        # 已有设备：更新 last_seen（强制使用服务器时间）和所有健康字段
        device.last_seen = now
        device.is_demo = False  # 收到真实心跳即标记非演示
        _apply_device_heartbeat(device, req)
    else:
        # 新设备：创建，标记为非演示设备
        device = Device(
            name=req.device_id,
            last_seen=now,
            first_seen=now,
            is_demo=False,
        )
        _apply_device_heartbeat(device, req)
        db.add(device)

    db.commit()
    db.refresh(device)

    return ApiResponse(
        status="success",
        code=200,
        message="心跳已接收",
        data={
            "server_time": now.isoformat(),
            "device_id": device.name,
            "online_status": "online",
        },
    )
