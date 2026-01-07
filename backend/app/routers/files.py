import os
import pathlib
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import bili_dao
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

class FileInfo(BaseModel):
    """文件信息模型"""
    filename: str
    path: str
    size: int
    modified_at: str
    source: str = "upload"  # upload, bilibili
    metadata: Optional[dict] = None

@router.get("/files/videos")
async def list_video_files():
    """列出所有可用视频文件"""
    try:
        # 定义上传目录
        upload_dir = pathlib.Path("uploads")
        if not upload_dir.exists():
            return {"success": True, "data": []}
            
        # 获取所有 B站下载历史记录，用于匹配
        bili_history = bili_dao.get_bili_download_history(limit=100)
        bili_map = {}
        for item in bili_history:
            # 记录文件名 -> 历史记录的映射
            if item.file_path:
                try:
                    p = pathlib.Path(item.file_path)
                    bili_map[p.name] = item
                except:
                    pass
        
        files = []
        # 扩展名过滤
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        
        for file_path in upload_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                stats = file_path.stat()
                filename = file_path.name
                
                # 判断来源
                is_bili = filename in bili_map
                source = "bilibili" if is_bili else "upload"
                
                # 附加元数据
                meta = None
                if is_bili:
                    history = bili_map[filename]
                    meta = {
                        "title": history.title,
                        "bv_id": history.bv_id,
                        "quality": history.quality
                    }
                
                files.append({
                    "filename": filename,
                    "path": str(file_path),
                    "size": stats.st_size,
                    "modified_at": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    "source": source,
                    "metadata": meta
                })
        
        # 按修改时间倒序排序
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return {"success": True, "data": files}
        
    except Exception as e:
        logger.error(f"获取视频文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
