import os
import pathlib
import re
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
        # 下载器把 B 站视频保存到 UPLOAD_DIR（应用数据目录），
        # 媒体库必须扫同一个目录，否则看不到新下载的视频
        upload_dir = pathlib.Path(os.getenv("UPLOAD_DIR", "uploads"))
        if not upload_dir.exists():
            return {"success": True, "data": []}

        # 获取所有 B站下载历史记录，用于匹配
        bili_history = bili_dao.get_bili_download_history(limit=500)
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

        # 先收集非任务副本文件的 (大小 -> 文件名) 映射：
        # 从媒体库创建任务会把视频复制为 {任务ID}.mp4，这些副本不需要重复展示
        task_copy_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
        named_files = {}
        for file_path in upload_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                if not task_copy_pattern.match(file_path.stem):
                    named_files.setdefault(file_path.stat().st_size, file_path.name)

        for file_path in upload_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                filename = file_path.name
                # 任务副本且存在同大小的原始命名文件时跳过
                if task_copy_pattern.match(file_path.stem) and named_files.get(file_path.stat().st_size):
                    continue

                stats = file_path.stat()
                
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
