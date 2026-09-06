# -*- coding: utf-8 -*-
"""
Bilibili 数据模型
"""

from pydantic import BaseModel, Field


class VideoUrlInfo(BaseModel):
    """Bilibili 视频 URL 信息"""
    video_id: str = Field(title="视频ID (BV号)")
    page: int = Field(default=1, title="分P序号，从1开始")
    video_type: str = Field(default="video", title="视频类型")
