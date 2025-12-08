"""
数据库迁移脚本
用于添加新字段到现有数据库
"""
import sqlite3
from pathlib import Path
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
except:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./video_note.db")
# 处理相对路径和绝对路径
if DATABASE_URL.startswith("sqlite:///"):
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
    # 如果是相对路径，转换为绝对路径
    if not os.path.isabs(DB_PATH):
        DB_PATH = os.path.join(os.getcwd(), DB_PATH)
else:
    DB_PATH = DATABASE_URL


def migrate_add_screenshot_column():
    """添加 screenshot 字段到 video_tasks 表"""
    if not Path(DB_PATH).exists():
        logger.info("数据库不存在，将在首次运行时自动创建")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(video_tasks)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "screenshot" not in columns:
            logger.info("添加 screenshot 字段到 video_tasks 表...")
            cursor.execute("ALTER TABLE video_tasks ADD COLUMN screenshot INTEGER DEFAULT 0")
            conn.commit()
            logger.info("✓ screenshot 字段添加成功")
        else:
            logger.info("screenshot 字段已存在，跳过迁移")
        
        conn.close()
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        raise


if __name__ == "__main__":
    migrate_add_screenshot_column()

