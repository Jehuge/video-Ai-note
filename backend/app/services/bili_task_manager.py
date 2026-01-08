"""
B站下载任务管理器
改编自 bili-crawler/task_manager.py
"""

import asyncio
from typing import Optional, Dict, List, Callable, Awaitable
from enum import Enum
import uuid

from app.utils.bili_logger import logger


class TaskStatus(Enum):
    """任务状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


# 定义回调类型
LogCallback = Callable[[str, str], Awaitable[None]]
ProgressCallback = Callable[[str, str, int, int, int], Awaitable[None]]
StatusCallback = Callable[[str, str], Awaitable[None]]


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
        
        # WebSocket 回调
        self._log_callback: Optional[LogCallback] = None
        self._progress_callback: Optional[ProgressCallback] = None
        self._status_callback: Optional[StatusCallback] = None
    
    def set_log_callback(self, callback: LogCallback):
        """设置日志回调"""
        self._log_callback = callback
    
    def set_progress_callback(self, callback: ProgressCallback):
        """设置进度回调"""
        self._progress_callback = callback
    
    def set_status_callback(self, callback: StatusCallback):
        """设置状态变更回调"""
        self._status_callback = callback
    
    async def emit_log(self, level: str, message: str):
        """发送日志"""
        logger.info(f"[{level.upper()}] {message}")
        if self._log_callback:
            try:
                await self._log_callback(level, message)
            except Exception as e:
                logger.error(f"日志回调错误: {e}")
    
    async def emit_progress(self):
        """发送进度更新"""
        if self._progress_callback:
            try:
                await self._progress_callback(
                    self.status.value,
                    self.current_video or "",
                    self.total_videos,
                    self.completed_videos,
                    self.download_progress
                )
            except Exception as e:
                logger.error(f"进度回调错误: {e}")
    
    async def emit_status_change(self, message: str = ""):
        """发送状态变更"""
        if self._status_callback:
            try:
                await self._status_callback(self.status.value, message)
            except Exception as e:
                logger.error(f"状态回调错误: {e}")
    
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
        self.download_progress = 0
        
        await self.emit_status_change("下载任务启动")
        await self.emit_log("info", f"开始下载任务，共 {self.total_videos} 个视频")
        await self.emit_progress()
        
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
            await self.emit_status_change("下载完成")
            await self.emit_log("success", "所有下载任务完成!")
            await self.emit_progress()
            
        except asyncio.CancelledError:
            self.status = TaskStatus.STOPPED
            await self.emit_status_change("任务已取消")
            await self.emit_log("warning", "下载任务已取消")
            
        except Exception as e:
            self.status = TaskStatus.STOPPED
            await self.emit_status_change("下载出错")
            await self.emit_log("error", f"下载任务出错: {e}")
            logger.error(f"下载任务异常: {e}", exc_info=True)
    
    async def stop_download(self):
        """停止下载任务"""
        if self.status == TaskStatus.RUNNING and self.download_task:
            self.status = TaskStatus.STOPPED
            self.download_task.cancel()
            await self.emit_status_change("正在停止")
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
    
    async def update_progress(self, current_video: str, completed: int, progress: int = 0):
        """更新下载进度（异步版本）"""
        self.current_video = current_video
        self.completed_videos = completed
        self.download_progress = progress
        await self.emit_progress()
    
    def update_progress_sync(self, current_video: str, completed: int, progress: int = 0):
        """更新下载进度（同步版本，兼容旧代码）"""
        self.current_video = current_video
        self.completed_videos = completed
        self.download_progress = progress


# 全局任务管理器实例
task_manager = BiliTaskManager()
