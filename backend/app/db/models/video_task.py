from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.engine import Base


class VideoTask(Base):
    """视频任务表"""
    __tablename__ = "video_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    markdown = Column(String, nullable=True)
    screenshot = Column(Integer, default=0)  # 0=False, 1=True
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

