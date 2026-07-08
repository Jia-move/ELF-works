"""WebSocket 连接管理器"""
from fastapi import WebSocket
from typing import List
import json


class WebSocketManager:
    """管理所有 WebSocket 客户端连接"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """向所有连接的客户端广播消息"""
        payload = json.dumps(message, ensure_ascii=False, default=str)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


# 全局单例
ws_manager = WebSocketManager()
