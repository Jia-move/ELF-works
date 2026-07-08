"""景点知识库管理"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ScenicSpot
from app.schemas import (
    ApiResponse,
    ScenicSpotCreate,
    ScenicSpotUpdate,
    ScenicSpotOut,
)

router = APIRouter(tags=["scenic-spots"])


@router.get("/api/scenic-spots", response_model=ApiResponse)
def list_scenic_spots(db: Session = Depends(get_db)):
    spots = db.query(ScenicSpot).order_by(ScenicSpot.id).all()
    return ApiResponse(
        status="success",
        code=200,
        message="OK",
        data={"list": [ScenicSpotOut.model_validate(s).model_dump() for s in spots]},
    )


@router.post("/api/scenic-spots", response_model=ApiResponse)
def create_scenic_spot(req: ScenicSpotCreate, db: Session = Depends(get_db)):
    existing = db.query(ScenicSpot).filter(ScenicSpot.class_name == req.class_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="景点类别名已存在")

    spot = ScenicSpot(**req.model_dump())
    db.add(spot)
    db.commit()
    db.refresh(spot)

    return ApiResponse(
        status="success",
        code=200,
        message="创建成功",
        data=ScenicSpotOut.model_validate(spot).model_dump(),
    )


@router.put("/api/scenic-spots/{spot_id}", response_model=ApiResponse)
def update_scenic_spot(spot_id: int, req: ScenicSpotUpdate, db: Session = Depends(get_db)):
    spot = db.query(ScenicSpot).filter(ScenicSpot.id == spot_id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="景点不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(spot, key, value)
    spot.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(spot)

    return ApiResponse(
        status="success",
        code=200,
        message="更新成功",
        data=ScenicSpotOut.model_validate(spot).model_dump(),
    )


@router.delete("/api/scenic-spots/{spot_id}", response_model=ApiResponse)
def delete_scenic_spot(spot_id: int, db: Session = Depends(get_db)):
    spot = db.query(ScenicSpot).filter(ScenicSpot.id == spot_id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="景点不存在")

    db.delete(spot)
    db.commit()

    return ApiResponse(
        status="success",
        code=200,
        message="删除成功",
        data=None,
    )
