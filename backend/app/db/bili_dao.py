"""
B站下载数据访问对象 (DAO)
遵循原项目的 DAO 模式
"""
import json
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.engine import SessionLocal
from app.db.models.bili_config import BiliConfig
from app.db.models.bili_video import BiliVideo
from app.db.models.bili_download_history import BiliDownloadHistory
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 配置管理 ====================

def set_default_bili_config():
    """设置默认配置"""
    default_config = {
        "video_quality": 80,  # 1080p
        "download_path": "uploads",  # 下载到 uploads 目录
        "download_interval": 2,  # 下载间隔2秒
        "headless": False,  # 不使用无头模式
    }
    
    db = SessionLocal()
    try:
        for key, value in default_config.items():
            # 检查是否已存在
            existing = db.query(BiliConfig).filter(BiliConfig.key == key).first()
            if not existing:
                config = BiliConfig(key=key, value=json.dumps(value))
                db.add(config)
        db.commit()
        logger.info("B站下载默认配置已设置")
    except Exception as e:
        db.rollback()
        logger.error(f"设置默认配置失败: {e}")
        raise
    finally:
        db.close()


def get_bili_config() -> Dict:
    """获取所有配置"""
    db = SessionLocal()
    try:
        configs = db.query(BiliConfig).all()
        result = {}
        for config in configs:
            result[config.key] = json.loads(config.value)
        return result
    finally:
        db.close()


def update_bili_config(config: Dict):
    """更新配置"""
    db = SessionLocal()
    try:
        for key, value in config.items():
            existing = db.query(BiliConfig).filter(BiliConfig.key == key).first()
            if existing:
                existing.value = json.dumps(value)
                existing.updated_at = func.now()
            else:
                new_config = BiliConfig(key=key, value=json.dumps(value))
                db.add(new_config)
        db.commit()
        logger.info("B站下载配置已更新")
    except Exception as e:
        db.rollback()
        logger.error(f"更新配置失败: {e}")
        raise
    finally:
        db.close()


# ==================== 视频管理 ====================

def create_bili_video(bv_id: str, url: str = "") -> BiliVideo:
    """添加视频到列表"""
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.query(BiliVideo).filter(BiliVideo.bv_id == bv_id).first()
        if existing:
            raise ValueError(f"视频 {bv_id} 已存在")
        
        video = BiliVideo(
            bv_id=bv_id,
            url=url,
            status="pending"
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        logger.info(f"已添加视频: {bv_id}")
        return video
    except Exception as e:
        db.rollback()
        logger.error(f"添加视频失败: {e}")
        raise
    finally:
        db.close()


def get_bili_videos() -> List[BiliVideo]:
    """获取所有视频"""
    db = SessionLocal()
    try:
        return db.query(BiliVideo).order_by(BiliVideo.created_at.desc()).all()
    finally:
        db.close()


def get_bili_video_by_bvid(bv_id: str) -> Optional[BiliVideo]:
    """根据BV号获取视频"""
    db = SessionLocal()
    try:
        return db.query(BiliVideo).filter(BiliVideo.bv_id == bv_id).first()
    finally:
        db.close()


def update_bili_video_status(bv_id: str, status: str, title: str = None):
    """更新视频状态"""
    db = SessionLocal()
    try:
        video = db.query(BiliVideo).filter(BiliVideo.bv_id == bv_id).first()
        if video:
            video.status = status
            if title:
                video.title = title
            video.updated_at = func.now()
            db.commit()
            db.refresh(video)
            logger.info(f"更新视频状态: {bv_id} -> {status}")
            return video
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"更新视频状态失败: {e}")
        raise
    finally:
        db.close()


def delete_bili_video(video_id: int) -> bool:
    """删除视频"""
    db = SessionLocal()
    try:
        video = db.query(BiliVideo).filter(BiliVideo.id == video_id).first()
        if video:
            db.delete(video)
            db.commit()
            logger.info(f"已删除视频 ID: {video_id}")
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"删除视频失败: {e}")
        raise
    finally:
        db.close()


def clear_bili_videos():
    """清空视频列表"""
    db = SessionLocal()
    try:
        db.query(BiliVideo).delete()
        db.commit()
        logger.info("已清空视频列表")
    except Exception as e:
        db.rollback()
        logger.error(f"清空视频列表失败: {e}")
        raise
    finally:
        db.close()


# ==================== 下载历史 ====================

def add_bili_download_history(
    bv_id: str,
    title: str,
    file_path: str,
    file_size: int,
    quality: int
) -> BiliDownloadHistory:
    """添加下载历史"""
    db = SessionLocal()
    try:
        history = BiliDownloadHistory(
            bv_id=bv_id,
            title=title,
            file_path=file_path,
            file_size=file_size,
            quality=quality
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        logger.info(f"已添加下载历史: {bv_id}")
        return history
    except Exception as e:
        db.rollback()
        logger.error(f"添加下载历史失败: {e}")
        raise
    finally:
        db.close()


def get_bili_download_history(limit: int = 50) -> List[BiliDownloadHistory]:
    """获取下载历史"""
    db = SessionLocal()
    try:
        return db.query(BiliDownloadHistory).order_by(
            BiliDownloadHistory.downloaded_at.desc()
        ).limit(limit).all()
    finally:
        db.close()
