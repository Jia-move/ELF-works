"""Dashboard 汇总"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Device, ScenicSpot, RecognitionEvent, QARecord
from app.routers.devices import compute_online_status
from app.schemas import ApiResponse

router = APIRouter(tags=["dashboard"])


def _is_real_device(device: Device) -> bool:
    """过滤测试设备：排除 name 中包含 test/mock/review 关键词的设备"""
    name_lower = (device.name or "").lower()
    exclude_keywords = ["test", "mock", "review", "demo-device"]
    return not any(k in name_lower for k in exclude_keywords)


@router.get("/api/dashboard/summary", response_model=ApiResponse)
def dashboard_summary(db: Session = Depends(get_db)):
    all_devices = db.query(Device).all()
    real_devices = [d for d in all_devices if _is_real_device(d)]
    total_devices = len(real_devices)
    online_devices = sum(1 for d in real_devices if compute_online_status(d) == "online")
    total_recognitions = db.query(RecognitionEvent).count()
    total_qa_records = db.query(QARecord).count()

    # 预加载 domain 映射
    spots_map = {s.class_name: s.domain for s in db.query(ScenicSpot).all()}

    # 最近一次识别（当前导览目标）
    latest = (
        db.query(RecognitionEvent)
        .order_by(desc(RecognitionEvent.timestamp))
        .first()
    )
    current_scenic_spot = None
    if latest:
        current_scenic_spot = {
            "class_name": latest.class_name,
            "display_name": latest.display_name,
            "confidence": latest.confidence,
            "timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
            "device_id": latest.device_id,
            "domain": spots_map.get(latest.class_name, None),
        }

    # 最近 10 条识别记录
    recent = (
        db.query(RecognitionEvent)
        .order_by(desc(RecognitionEvent.timestamp))
        .limit(10)
        .all()
    )
    recent_recognitions = [
        {
            "id": r.id,
            "device_id": r.device_id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "class_name": r.class_name,
            "display_name": r.display_name,
            "confidence": r.confidence,
            "narration_triggered": r.narration_triggered,
            "source": r.source,
            "domain": spots_map.get(r.class_name, None),
        }
        for r in recent
    ]

    return ApiResponse(
        status="success",
        code=200,
        message="OK",
        data={
            "total_devices": total_devices,
            "online_devices": online_devices,
            "total_recognitions": total_recognitions,
            "total_qa_records": total_qa_records,
            "current_scenic_spot": current_scenic_spot,
            "recent_recognitions": recent_recognitions,
        },
    )
