"""Smart Guide Web - FastAPI 主入口"""
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# 加载 .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from app.database import init_db, run_migrations
from app.seed import seed_data
from app.websocket_manager import ws_manager
from app.routers import health, dashboard, devices, scenic_spots, recognitions, qa_records


# ========== 请求日志中间件 ==========

class RequestLogMiddleware(BaseHTTPMiddleware):
    """记录 method, path, client_ip, status_code, duration_ms"""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)
        client_ip = request.client.host if request.client else "unknown"
        ts = datetime.now(timezone.utc).isoformat()
        print(
            f"[{ts}] {client_ip} {request.method} {request.url.path} -> "
            f"{response.status_code} ({duration_ms}ms)"
        )
        return response


# ========== 应用生命周期 ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：初始化数据库、执行迁移、填充模拟数据"""
    init_db()
    run_migrations()
    seed_data()
    yield


app = FastAPI(
    title="Smart Guide Web",
    description="RK3588 智能导览眼镜 - 本地 Web 管理端",
    version="1.0.0",
    lifespan=lifespan,
)

# 请求日志中间件
app.add_middleware(RequestLogMiddleware)

# CORS — 本地 MVP 允许所有来源（LAN 访问需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 统一异常处理 ==========

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """将 HTTPException 转为统一错误格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": exc.detail if isinstance(exc.detail, str) else "请求错误",
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """将 Pydantic 校验错误转为统一格式，data 中保留字段详情"""
    errors = []
    for err in exc.errors():
        errors.append({
            "loc": err.get("loc", []),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "code": 422,
            "message": "请求数据校验失败",
            "data": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未处理异常：不泄露堆栈到客户端，终端记录完整异常"""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
        },
    )


# 注册路由
app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(devices.router)
app.include_router(scenic_spots.router)
app.include_router(recognitions.router)
app.include_router(qa_records.router)


# WebSocket
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
