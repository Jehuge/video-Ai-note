from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.engine import Base


class BiliVideo(Base):
    """B站视频列表表"""
    __tablename__ = "bili_videos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bv_id = Column(String, unique=True, nullable=False, index=True)
    url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, downloaded, failed
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
