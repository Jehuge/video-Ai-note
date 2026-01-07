from sqlalchemy import Column, String, DateTime, func
from app.db.engine import Base


class BiliConfig(Base):
    """B站下载配置表"""
    __tablename__ = "bili_config"
    
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
