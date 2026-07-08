# 后端服务说明

后端使用 FastAPI + SQLite，负责接收 RK3588 端上传的数据并为前端提供 API。

## 环境要求

- Python 3.10+
- Windows PowerShell

## 安装依赖

```powershell
cd C:\Users\33347\Desktop\web\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 启动服务

```powershell
cd C:\Users\33347\Desktop\web\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后访问：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/docs
```

## 本地数据库

默认数据库文件：

```text
backend/data/smart_guide.db
```

服务启动时会自动建表，并写入基础演示数据。

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/dashboard/summary` | 系统总览 |
| GET | `/api/devices` | 设备列表 |
| POST | `/api/devices/heartbeat` | 设备心跳 |
| GET | `/api/scenic-spots` | 导览内容列表 |
| POST | `/api/scenic-spots` | 新增导览内容 |
| PUT | `/api/scenic-spots/{id}` | 更新导览内容 |
| DELETE | `/api/scenic-spots/{id}` | 删除导览内容 |
| GET | `/api/recognitions` | 识别记录列表 |
| POST | `/api/device/events` | 接收识别事件 |
| GET | `/api/qa-records` | 问答记录列表 |
| POST | `/api/qa-records` | 接收问答记录 |
| WS | `/ws/events` | 实时事件推送 |

## 模拟识别事件

后端运行时，可以另开一个 PowerShell 执行：

```powershell
cd C:\Users\33347\Desktop\web\backend
.\.venv\Scripts\Activate.ps1
python scripts\send_demo_event.py
```
