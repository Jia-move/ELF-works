"""识别记录 & 设备事件接收"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Device, RecognitionEvent, ScenicSpot
from app.schemas import (
    ApiResponse,
    RecognitionEventCreate,
    RecognitionEventOut,
)
from app.websocket_manager import ws_manager

router = APIRouter(tags=["recognitions"])


@router.get("/api/recognitions", response_model=ApiResponse)
def list_recognitions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(RecognitionEvent)
    if device_id:
        query = query.filter(RecognitionEvent.device_id == device_id)

    total = query.count()
    events = (
        query.order_by(desc(RecognitionEvent.timestamp))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 预加载所有导览内容以获取 domain 映射
    spots = {s.class_name: s.domain for s in db.query(ScenicSpot).all()}

    def _enrich(event):
        out = RecognitionEventOut.model_validate(event).model_dump()
        out["domain"] = spots.get(event.class_name, None)
        return out

    return ApiResponse(
        status="success",
        code=200,
        message="OK",
        data={
            "list": [_enrich(e) for e in events],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.post("/api/device/events", response_model=ApiResponse)
async def receive_device_event(req: RecognitionEventCreate, db: Session = Depends(get_db)):
    """接收设备推送的识别事件 — 支持 event_id 幂等去重"""
    now = datetime.now(timezone.utc)

    # 1. 幂等去重：event_id 已存在则跳过入库
    if req.event_id:
        existing = (
            db.query(RecognitionEvent)
            .filter(RecognitionEvent.event_id == req.event_id)
            .first()
        )
        if existing:
            return ApiResponse(
                status="success",
                code=200,
                message="事件已存在（重复提交已忽略）",
                data={"event_id": req.event_id, "is_duplicate": True},
            )

    # 2. 更新设备 last_seen（强制使用服务器接收时间）
    device = db.query(Device).filter(Device.name == req.device_id).first()
    if device:
        device.last_seen = now
        # 真实来源（非 demo）标记为非演示设备
        if req.source != "demo":
            device.is_demo = False
    else:
        device = Device(
            name=req.device_id,
            last_seen=now,
            first_seen=now,
            is_demo=(req.source == "demo"),
        )
        db.add(device)
    db.commit()

    # 3. 映射 captured_at → DB 列 timestamp，添加 received_at
    event_data = req.model_dump()
    event_data["timestamp"] = event_data.pop("captured_at")
    event_data["received_at"] = now

    # 4. 保存识别记录
    event = RecognitionEvent(**event_data)
    db.add(event)
    db.commit()
    db.refresh(event)

    event_out = RecognitionEventOut.model_validate(event).model_dump()
    # 转换时间戳为 ISO 字符串（前端兼容）
    if event.timestamp:
        event_out["timestamp"] = event.timestamp.isoformat()

    # 补充 domain 信息（从导览内容库查找）
    spot = db.query(ScenicSpot).filter(ScenicSpot.class_name == event.class_name).first()
    event_out["domain"] = spot.domain if spot else None

    # 5. 通过 WebSocket 推送给前端
    await ws_manager.broadcast(
        {
            "type": "recognition_event",
            "data": event_out,
        }
    )

    return ApiResponse(
        status="success",
        code=200,
        message="事件已接收",
        data=event_out,
    )
