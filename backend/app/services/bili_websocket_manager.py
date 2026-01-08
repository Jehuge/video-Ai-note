"""
WebSocket 连接管理器
用于实时日志推送和下载进度更新
"""

from typing import List, Dict, Any
from datetime import datetime
from fastapi import WebSocket

from app.utils.bili_logger import logger


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """接受 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 客户端连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 客户端断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                disconnected.append(connection)
        
        # 移除失败的连接
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
    
    async def send_log(self, level: str, message: str):
        """发送日志消息"""
        await self.broadcast({
            "type": "log",
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        })
    
    async def send_progress(self, status: str, current_video: str, 
                           total: int, completed: int, progress: int = 0):
        """发送下载进度"""
        await self.broadcast({
            "type": "progress",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "status": status,
                "current_video": current_video,
                "total": total,
                "completed": completed,
                "progress": progress
            }
        })
    
    async def send_status_change(self, status: str, message: str = ""):
        """发送状态变更通知"""
        await self.broadcast({
            "type": "status",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "message": message
        })


# 全局连接管理器实例
connection_manager = ConnectionManager()
