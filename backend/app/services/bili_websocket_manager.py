"""
WebSocket 连接管理器
用于实时日志推送
"""

from typing import List
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


# 全局连接管理器实例
connection_manager = ConnectionManager()
