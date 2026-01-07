"""
B站下载任务管理器
改编自 bili-crawler/task_manager.py
"""

import asyncio
from typing import Optional, Dict, List
from enum import Enum
import uuid

from app.utils.bili_logger import logger


class TaskStatus(Enum):
    """任务状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class BiliTaskManager:
    """B站下载任务管理器"""
    
    def __init__(self):
        self.status = TaskStatus.IDLE
        self.current_task_id: Optional[str] = None
        self.current_video: Optional[str] = None
        self.total_videos: int = 0
        self.completed_videos: int = 0
        self.download_progress: int = 0  # 当前视频下载进度 0-100
        self.downloader = None
        self.download_task: Optional[asyncio.Task] = None
        self.log_callbacks: List = []
        
    def add_log_callback(self, callback):
        """添加日志回调函数"""
        self.log_callbacks.append(callback)
    
    async def emit_log(self, level: str, message: str):
        """发送日志到所有回调"""
        for callback in self.log_callbacks:
            try:
                await callback(level, message)
            except Exception as e:
                logger.error(f"日志回调错误: {e}")
    
    async def start_download(self, video_list: List[str], config: Dict) -> str:
        """
        启动下载任务
        
        Args:
            video_list: 视频BV号列表
            config: 配置字典
        
        Returns:
            任务ID
        """
        if self.status == TaskStatus.RUNNING:
            raise RuntimeError("已有任务在运行中")
        
        self.current_task_id = str(uuid.uuid4())
        self.status = TaskStatus.RUNNING
        self.total_videos = len(video_list)
        self.completed_videos = 0
        
        await self.emit_log("info", f"开始下载任务，共 {self.total_videos} 个视频")
        
        # 创建下载任务
        self.download_task = asyncio.create_task(
            self._run_download(video_list, config)
        )
        
        return self.current_task_id
    
    async def _run_download(self, video_list: List[str], config: Dict):
        """执行下载任务"""
        try:
            # 动态导入下载器
            from app.services.bilibili.downloader import BilibiliDownloader
            
            self.downloader = BilibiliDownloader()
            
            # 设置下载器配置
            self.downloader.set_config(config)
            self.downloader.set_video_list(video_list)
            self.downloader.set_task_manager(self)
            
            # 启动下载器
            await self.downloader.start()
            
            self.status = TaskStatus.IDLE
            await self.emit_log("success", "所有下载任务完成!")
            
        except Exception as e:
            self.status = TaskStatus.STOPPED
            await self.emit_log("error", f"下载任务出错: {e}")
            logger.error(f"下载任务异常: {e}", exc_info=True)
    
    async def stop_download(self):
        """停止下载任务"""
        if self.status == TaskStatus.RUNNING and self.download_task:
            self.status = TaskStatus.STOPPED
            self.download_task.cancel()
            await self.emit_log("warning", "下载任务已停止")
            
            # 清理下载器
            if self.downloader:
                try:
                    await self.downloader.cleanup()
                except Exception as e:
                    logger.error(f"清理下载器时出错: {e}")
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            "status": self.status.value,
            "task_id": self.current_task_id,
            "current_video": self.current_video,
            "total": self.total_videos,
            "completed": self.completed_videos,
            "progress": self.download_progress,
        }
    
    def update_progress(self, current_video: str, completed: int, progress: int = 0):
        """更新下载进度"""
        self.current_video = current_video
        self.completed_videos = completed
        self.download_progress = progress


# 全局任务管理器实例
task_manager = BiliTaskManager()
