from sqlalchemy.orm import Session
from app.db.engine import SessionLocal
from app.db.models.video_task import VideoTask
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_task(task_id: str, filename: str, screenshot: bool = False) -> VideoTask:
    """创建新任务"""
    db = SessionLocal()
    try:
        task = VideoTask(
            task_id=task_id,
            filename=filename,
            status="pending",
            screenshot=1 if screenshot else 0
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    except Exception as e:
        db.rollback()
        logger.error(f"创建任务失败: {e}")
        raise
    finally:
        db.close()


def get_task_by_id(task_id: str) -> VideoTask:
    """根据 task_id 获取任务"""
    db = SessionLocal()
    try:
        task = db.query(VideoTask).filter(VideoTask.task_id == task_id).first()
        # 如果任务存在但没有 screenshot 字段，设置默认值
        if task and not hasattr(task, 'screenshot'):
            task.screenshot = 0
        return task
    finally:
        db.close()


def update_task_status(task_id: str, status: str, markdown: str = None):
    """更新任务状态"""
    db = SessionLocal()
    try:
        task = db.query(VideoTask).filter(VideoTask.task_id == task_id).first()
        if task:
            task.status = status
            if markdown:
                task.markdown = markdown
            db.commit()
            db.refresh(task)
            return task
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"更新任务状态失败: {e}")
        raise
    finally:
        db.close()


def get_all_tasks(limit: int = 50):
    """获取所有任务"""
    db = SessionLocal()
    try:
        return db.query(VideoTask).order_by(VideoTask.created_at.desc()).limit(limit).all()
    finally:
        db.close()

