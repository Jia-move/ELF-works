# 智能导览眼镜 Web 管理端

本项目是 RK3588 智能导览眼镜演示系统的电脑端 Web 管理端，用于接收设备心跳、识别事件和问答记录，并提供浏览器管理页面。

## 项目结构

```text
web/
├── backend/          # FastAPI 后端服务
│   ├── app/          # API、数据库模型、WebSocket 推送
│   ├── data/         # 本地 SQLite 数据库
│   └── scripts/      # 本地演示脚本
└── frontend/         # Vue 3 + Element Plus 前端
    ├── public/
    └── src/
```

## 启动后端

```powershell
cd C:\Users\33347\Desktop\web\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 启动前端

```powershell
cd C:\Users\33347\Desktop\web\frontend
npm run serve -- --host 0.0.0.0
```

默认端口为 `8081`。手机或第二台电脑访问：

```text
http://电脑IP:8081
```

## RK3588 端上传配置

RK3588 视觉程序的 Web 上传地址应指向电脑后端：

```yaml
web_upload:
  enabled: true
  base_url: "http://电脑IP:8000"
  device_id: "elf2-01"
```

## 主要功能

- 系统总览：设备在线状态、最新识别目标、实时识别记录。
- 设备管理：展示 RK3588 心跳、模型名称、摄像头/NPU/Qt/问答状态。
- 导览识别记录：查看设备上传的目标识别事件。
- 导览内容库：维护类别名、展示名称、讲解文本和类型。
- 智能问答记录：查看端侧上传的用户问答记录。

## 常用接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 后端健康检查 |
| GET | `/api/dashboard/summary` | 系统总览 |
| GET | `/api/devices` | 设备列表 |
| POST | `/api/devices/heartbeat` | 设备心跳 |
| GET | `/api/scenic-spots` | 导览内容列表 |
| POST | `/api/scenic-spots` | 新增导览内容 |
| GET | `/api/recognitions` | 识别记录列表 |
| POST | `/api/device/events` | 接收识别事件 |
| GET | `/api/qa-records` | 问答记录列表 |
| POST | `/api/qa-records` | 接收问答记录 |
| WS | `/ws/events` | 实时事件推送 |
