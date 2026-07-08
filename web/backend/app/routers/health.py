"""健康检查"""
from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal
from app.schemas import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=ApiResponse)
def health_check():
    db_status = "disconnected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return ApiResponse(
        status="success",
        code=200,
        message="OK",
        data={
            "service": "smart-guide-web",
            "database": db_status,
        },
    )
