"""智能问答记录"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import QARecord
from app.schemas import ApiResponse, QARecordCreate, QARecordOut

router = APIRouter(tags=["qa-records"])


@router.get("/api/qa-records", response_model=ApiResponse)
def list_qa_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(QARecord)
    if device_id:
        query = query.filter(QARecord.device_id == device_id)

    total = query.count()
    records = (
        query.order_by(desc(QARecord.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ApiResponse(
        status="success",
        code=200,
        message="OK",
        data={
            "list": [QARecordOut.model_validate(r).model_dump() for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.post("/api/qa-records", response_model=ApiResponse)
def create_qa_record(req: QARecordCreate, db: Session = Depends(get_db)):
    record = QARecord(**req.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    return ApiResponse(
        status="success",
        code=200,
        message="记录已保存",
        data=QARecordOut.model_validate(record).model_dump(),
    )
