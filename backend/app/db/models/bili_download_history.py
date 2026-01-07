from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.engine import Base


class BiliDownloadHistory(Base):
    """B站下载历史表"""
    __tablename__ = "bili_download_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bv_id = Column(String, nullable=False)
    title = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)  # 文件大小(字节)
    quality = Column(Integer, nullable=True)  # 视频清晰度
    downloaded_at = Column(DateTime, server_default=func.now())
