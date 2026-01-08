"""
B站视频下载 API 路由
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.db import bili_dao
from app.services.bili_task_manager import task_manager
from app.services.bili_websocket_manager import connection_manager
from app.services.bilibili.help import parse_video_info_from_url
from app.utils.bili_logger import logger

router = APIRouter()


# ==================== 初始化 WebSocket 回调 ====================

def _setup_websocket_callbacks():
    """设置 WebSocket 回调函数"""
    task_manager.set_log_callback(connection_manager.send_log)
    task_manager.set_progress_callback(connection_manager.send_progress)
    task_manager.set_status_callback(connection_manager.send_status_change)

# 模块加载时初始化回调
_setup_websocket_callbacks()


# ==================== 数据模型 ====================

class ConfigUpdate(BaseModel):
    """配置更新模型"""
    video_quality: Optional[int] = None
    download_path: Optional[str] = None
    download_interval: Optional[int] = None
    headless: Optional[bool] = None


class VideoAdd(BaseModel):
    """添加视频模型"""
    url: str


class DownloadStart(BaseModel):
    """开始下载模型"""
    video_ids: Optional[List[int]] = None  # None 表示下载所有


# ==================== API 端点 ====================

@router.get("/bili/config")
async def get_config():
    """获取当前配置"""
    try:
        config = bili_dao.get_bili_config()
        return {"success": True, "data": config}
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bili/config")
async def update_config(config: ConfigUpdate):
    """更新配置"""
    try:
        # 只更新提供的字段
        config_dict = {k: v for k, v in config.dict().items() if v is not None}
        if config_dict:
            bili_dao.update_bili_config(config_dict)
        
        await connection_manager.send_log("info", "配置已更新")
        
        return {"success": True, "message": "配置更新成功"}
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bili/videos")
async def get_videos():
    """获取视频列表"""
    try:
        videos = bili_dao.get_bili_videos()
        # 转换为字典列表
        video_list = []
        for video in videos:
            video_list.append({
                "id": video.id,
                "bv_id": video.bv_id,
                "url": video.url,
                "title": video.title,
                "status": video.status,
                "created_at": video.created_at.isoformat() if video.created_at else None
            })
        return {"success": True, "data": video_list}
    except Exception as e:
        logger.error(f"获取视频列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bili/videos")
async def add_video(video: VideoAdd):
    """添加视频"""
    try:
        # 解析视频信息
        video_info = parse_video_info_from_url(video.url)
        bv_id = video_info.video_id
        
        # 添加到数据库
        result = bili_dao.create_bili_video(bv_id=bv_id, url=video.url)
        
        await connection_manager.send_log("info", f"已添加视频: {bv_id}")
        
        return {
            "success": True,
            "data": {
                "id": result.id,
                "bv_id": result.bv_id,
                "url": result.url,
                "status": result.status
            },
            "message": "视频添加成功"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"添加视频失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bili/videos/{video_id}")
async def delete_video(video_id: int):
    """删除视频"""
    try:
        success = bili_dao.delete_bili_video(video_id)
        if not success:
            raise HTTPException(status_code=404, detail="视频不存在")
        
        await connection_manager.send_log("info", f"已删除视频 ID: {video_id}")
        
        return {"success": True, "message": "视频删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除视频失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bili/videos")
async def clear_videos():
    """清空视频列表"""
    try:
        bili_dao.clear_bili_videos()
        
        await connection_manager.send_log("warning", "已清空视频列表")
        
        return {"success": True, "message": "视频列表已清空"}
    except Exception as e:
        logger.error(f"清空视频列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bili/download/start")
async def start_download(params: Optional[DownloadStart] = None):
    """开始下载"""
    try:
        # 获取视频列表
        videos = bili_dao.get_bili_videos()
        
        if not videos:
            raise HTTPException(status_code=400, detail="视频列表为空")
        
        # 筛选要下载的视频
        if params and params.video_ids:
            video_list = [v.bv_id for v in videos if v.id in params.video_ids and v.status == 'pending']
        else:
            video_list = [v.bv_id for v in videos if v.status == 'pending']
        
        if not video_list:
            raise HTTPException(status_code=400, detail="没有待下载的视频")
        
        # 获取配置
        config = bili_dao.get_bili_config()
        
        # 启动下载任务
        task_id = await task_manager.start_download(video_list, config)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"下载任务已启动，共 {len(video_list)} 个视频"
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动下载失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bili/download/stop")
async def stop_download():
    """停止下载"""
    try:
        await task_manager.stop_download()
        return {"success": True, "message": "下载任务已停止"}
    except Exception as e:
        logger.error(f"停止下载失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bili/download/status")
async def get_download_status():
    """获取下载状态"""
    try:
        status = task_manager.get_status()
        return {"success": True, "data": status}
    except Exception as e:
        logger.error(f"获取下载状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bili/history")
async def get_download_history(limit: int = 50):
    """获取下载历史"""
    try:
        history = bili_dao.get_bili_download_history(limit)
        history_list = []
        for h in history:
            history_list.append({
                "id": h.id,
                "bv_id": h.bv_id,
                "title": h.title,
                "file_path": h.file_path,
                "file_size": h.file_size,
                "quality": h.quality,
                "downloaded_at": h.downloaded_at.isoformat() if h.downloaded_at else None
            })
        return {"success": True, "data": history_list}
    except Exception as e:
        logger.error(f"获取下载历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket 端点 ====================

@router.websocket("/ws/bili/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket 日志和进度推送"""
    await connection_manager.connect(websocket)
    
    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.now().isoformat(),
            "message": "WebSocket 连接成功"
        })
        
        # 发送当前状态
        status = task_manager.get_status()
        await websocket.send_json({
            "type": "progress",
            "timestamp": datetime.now().isoformat(),
            "data": status
        })
        
        # 保持连接
        while True:
            # 接收心跳消息
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        connection_manager.disconnect(websocket)
